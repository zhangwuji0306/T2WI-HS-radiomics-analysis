#!/usr/bin/env Rscript
# Repeated nested CV for Model 1/2/3. All learned preprocessing is outer-fold local.

suppressPackageStartupMessages({
  library(glmnet)
  library(survival)
  library(yaml)
})

script_arg <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE))
script_dir <- dirname(script_arg)
source(file.path(script_dir, "03_imputation.R"))
root <- dirname(script_dir)
cfg <- yaml::read_yaml(file.path(root, "configs", "primary.yaml"))
dat <- read.csv(file.path(root, "output", "modeling_v2", "dataset_primary_raw_A_r.csv"),
                check.names = FALSE, fileEncoding = "UTF-8")
candidates <- read.csv(file.path(root, cfg$radiomics$candidate_source),
                       check.names = FALSE, fileEncoding = "UTF-8-BOM")
clinical <- unlist(cfg$clinical_variables, use.names = FALSE)
radiomics <- candidates$feature
stopifnot(!any(c("sex", "length_mm", "distance_mm") %in% clinical))

arg <- commandArgs(trailingOnly = TRUE)
repeats <- if (length(arg)) as.integer(arg[1]) else as.integer(cfg$validation$outer_repeats)
out_tag <- if (length(arg) >= 2L) as.character(arg[2]) else "v3_corrected"
outer_k <- as.integer(cfg$validation$outer_folds)
inner_k <- as.integer(cfg$validation$inner_folds)
m <- as.integer(cfg$imputation$m)
seed <- as.integer(cfg$seed)

make_folds <- function(event, k, seed) {
  set.seed(seed)
  fold <- integer(length(event))
  for (value in sort(unique(event))) {
    idx <- sample(which(event == value))
    fold[idx] <- rep(seq_len(k), length.out = length(idx))
  }
  fold
}

filter_and_scale <- function(train, valid, radiomics, icc, sd_min, corr_max) {
  sds <- vapply(train[, radiomics, drop = FALSE], sd, numeric(1), na.rm = TRUE)
  keep <- names(sds)[is.finite(sds) & sds >= sd_min]
  priority <- order(-icc[keep], keep)
  keep <- keep[priority]
  selected <- character()
  if (length(keep)) {
    cm <- abs(cor(train[, keep, drop = FALSE], use = "pairwise.complete.obs"))
    for (f in keep) {
      if (!length(selected) || all(cm[f, selected] <= corr_max)) selected <- c(selected, f)
    }
  }
  continuous <- intersect(c("age", "cea_log", "thickness_mm", "eid_mm"), names(train))
  scale_cols <- c(continuous, selected)
  mu <- vapply(train[, scale_cols, drop = FALSE], mean, numeric(1))
  ss <- vapply(train[, scale_cols, drop = FALSE], sd, numeric(1))
  ss[!is.finite(ss) | ss == 0] <- 1
  train[, scale_cols] <- sweep(sweep(train[, scale_cols, drop = FALSE], 2, mu, "-"), 2, ss, "/")
  valid[, scale_cols] <- sweep(sweep(valid[, scale_cols, drop = FALSE], 2, mu, "-"), 2, ss, "/")
  list(train = train, valid = valid, radiomics = selected, mean = mu, sd = ss)
}

fit_glmnet_cox <- function(x, y, penalty, foldid) {
  cv.glmnet(x, y, family = "cox", alpha = 1, foldid = foldid,
            penalty.factor = penalty, standardize = FALSE, type.measure = "deviance",
            lambda.min.ratio = 5e-2, maxit = 1000000L)
}

icc <- setNames(candidates$icc_A, candidates$feature)
predictions <- list(); complexity <- list(); cursor <- 1L
warnings_log <- data.frame(repeat_id = integer(), fold = integer(), imputation = integer(),
                           model = character(), message = character(),
                           stringsAsFactors = FALSE)
record_warning <- function(w, repeat_id, fold, imputation, model) {
  warnings_log <<- rbind(warnings_log, data.frame(
    repeat_id = as.integer(repeat_id), fold = as.integer(fold),
    imputation = as.integer(imputation), model = as.character(model),
    message = conditionMessage(w), stringsAsFactors = FALSE))
  invokeRestart("muffleWarning")
}
for (r in seq_len(repeats)) {
  outer <- make_folds(dat$DFS_event, outer_k, seed + r)
  for (fold in seq_len(outer_k)) {
    tr_idx <- which(outer != fold); va_idx <- which(outer == fold)
    imp <- withCallingHandlers(
      impute_fold(dat[tr_idx, , drop = FALSE], dat[va_idx, , drop = FALSE],
                  clinical, radiomics, m = m, maxit = cfg$imputation$maxit,
                  seed = seed + r * 1000L + fold),
      warning = function(w) record_warning(w, r, fold, 0L, "imputation"))

    # Model2 uses only complete radiomics candidates.  It is therefore fit
    # once per outer split, not once per clinical-data imputation.  Reusing
    # one inner split also prevents model-selection noise from being mistaken
    # for imputation uncertainty.
    prep_rad <- filter_and_scale(imp$train[[1]], imp$newdata[[1]], radiomics, icc,
                                 cfg$radiomics$variance_threshold,
                                 cfg$radiomics$correlation_threshold)
    rad <- prep_rad$radiomics
    inner <- make_folds(imp$train[[1]]$DFS_event, inner_k,
                        seed + r * 100000L + fold * 100L)
    fit2 <- NULL; nz2 <- 0L
    if (length(rad)) {
      x2_fit <- as.matrix(prep_rad$train[, rad, drop = FALSE])
      fit2 <- withCallingHandlers(
        fit_glmnet_cox(x2_fit, Surv(prep_rad$train$DFS_time,
                                    prep_rad$train$DFS_event),
                       rep(1, length(rad)), inner),
        warning = function(w) record_warning(w, r, fold, 0L, "model2"))
      nz2 <- sum(coef(fit2, s = "lambda.1se") != 0)
    }
    for (j in seq_len(m)) {
      prep <- filter_and_scale(imp$train[[j]], imp$newdata[[j]], radiomics, icc,
                               cfg$radiomics$variance_threshold,
                               cfg$radiomics$correlation_threshold)
      tr <- prep$train; va <- prep$valid; rad <- prep$radiomics

      fit1 <- withCallingHandlers(
        coxph(as.formula(paste("Surv(DFS_time, DFS_event) ~",
                               paste(clinical, collapse = "+"))), data = tr,
              ties = "breslow", x = TRUE),
        warning = function(w) record_warning(w, r, fold, j, "model1"))
      lp1 <- as.numeric(predict(fit1, newdata = va, type = "lp"))

      if (length(rad) && !is.null(fit2)) {
        xv2 <- as.matrix(va[, rad, drop = FALSE])
        lp2 <- as.numeric(predict(fit2, newx = xv2, s = "lambda.1se", type = "link"))
      } else {
        lp2 <- rep(0, nrow(va))
      }

      both <- c(clinical, rad)
      x3 <- as.matrix(tr[, both, drop = FALSE]); xv3 <- as.matrix(va[, both, drop = FALSE])
      fit3 <- withCallingHandlers(
        fit_glmnet_cox(x3, Surv(tr$DFS_time, tr$DFS_event),
                       c(rep(0, length(clinical)), rep(1, length(rad))), inner),
        warning = function(w) record_warning(w, r, fold, j, "model3"))
      lp3 <- as.numeric(predict(fit3, newx = xv3, s = "lambda.1se", type = "link"))

      predictions[[cursor]] <- data.frame(row = va_idx, repeat_id = r, fold = fold,
                                           imputation = j, DFS_time = va$DFS_time,
                                           DFS_event = va$DFS_event,
                                           lp_model1 = lp1, lp_model2 = lp2, lp_model3 = lp3)
      complexity[[cursor]] <- data.frame(repeat_id = r, fold = fold, imputation = j,
                                          radiomics_after_filter = length(rad),
                                          model2_nonzero = nz2,
                                          model3_radiomics_nonzero =
                                            sum(coef(fit3, s = "lambda.1se")[-seq_along(clinical)] != 0))
      cursor <- cursor + 1L
    }
  }
}
outdir <- file.path(root, "output", "primary", paste0("nested_cv_", out_tag))
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
write.csv(do.call(rbind, predictions), file.path(outdir, "oof_predictions.csv"), row.names = FALSE)
write.csv(do.call(rbind, complexity), file.path(outdir, "model_complexity.csv"), row.names = FALSE)
write.csv(warnings_log, file.path(outdir, "warnings.csv"), row.names = FALSE)
message("Nested CV complete. Repeats=", repeats, "; imputations=", m)
