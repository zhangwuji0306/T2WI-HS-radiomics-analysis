#!/usr/bin/env Rscript
# Quick three- and five-year DFS AUC check after the corrected nested-CV run.
# The full-A fits are locked before B predictions; B outcomes are never used
# in imputation, preprocessing, feature filtering, or lambda selection.

suppressPackageStartupMessages({
  library(glmnet)
  library(survival)
  library(timeROC)
  library(yaml)
})

script_arg <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE))
script_dir <- dirname(script_arg)
root <- dirname(script_dir)
cfg <- yaml::read_yaml(file.path(root, "configs", "primary.yaml"))
source(file.path(script_dir, "03_imputation.R"))

arg <- commandArgs(trailingOnly = TRUE)
cv_tag <- if (length(arg)) as.character(arg[1]) else "v3_corrected"

model_dir <- file.path(root, "output", "modeling_v2")
cv_dir <- file.path(root, "output", "primary", paste0("nested_cv_", cv_tag))
outdir <- file.path(root, "output", "primary", paste0("quick_check_", cv_tag))
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

dat_a <- read.csv(file.path(model_dir, "dataset_primary_raw_A_r.csv"),
                  check.names = FALSE, fileEncoding = "UTF-8")
dat_b <- read.csv(file.path(model_dir, "dataset_primary_raw_B_r.csv"),
                  check.names = FALSE, fileEncoding = "UTF-8")
candidates <- read.csv(file.path(root, cfg$radiomics$candidate_source),
                       check.names = FALSE, fileEncoding = "UTF-8-BOM")
clinical <- unlist(cfg$clinical_variables, use.names = FALSE)
radiomics <- candidates$feature
stopifnot(!any(c("sex", "length_mm", "distance_mm") %in% clinical))

outer_folds <- as.integer(cfg$validation$outer_folds)
inner_folds <- as.integer(cfg$validation$inner_folds)
m <- as.integer(cfg$imputation$m)
seed <- as.integer(cfg$seed)
sd_min <- as.numeric(cfg$radiomics$variance_threshold)
corr_max <- as.numeric(cfg$radiomics$correlation_threshold)

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

# The same fold-local imputation implementation is used for the full-A fit.
# The deployment branch receives B rows but excludes all B outcomes.
imp <- impute_fold(dat_a, dat_b, clinical, radiomics, m = m,
                   maxit = as.integer(cfg$imputation$maxit), seed = seed)

# Model2 has no missing predictors and is fitted once on full A.  Its inner
# fold assignment is fixed and is not varied with the clinical imputations.
prep_rad <- filter_and_scale(imp$train[[1]], imp$newdata[[1]], radiomics, icc,
                             sd_min, corr_max)
rad <- prep_rad$radiomics
inner <- make_folds(imp$train[[1]]$DFS_event, inner_folds, seed + 100000L)
fit2 <- NULL; nz2 <- 0L
if (length(rad)) {
  fit2 <- fit_glmnet_cox(as.matrix(prep_rad$train[, rad, drop = FALSE]),
                         Surv(prep_rad$train$DFS_time, prep_rad$train$DFS_event),
                         rep(1, length(rad)), inner)
  nz2 <- sum(as.numeric(coef(fit2, s = "lambda.1se")) != 0)
}

pred_rows <- vector("list", m)
complexity <- vector("list", m)
for (j in seq_len(m)) {
  prep <- filter_and_scale(imp$train[[j]], imp$newdata[[j]], radiomics, icc,
                           sd_min, corr_max)
  tr <- prep$train
  nw <- prep$valid
  rad <- prep$radiomics
  y <- Surv(tr$DFS_time, tr$DFS_event)

  fit1 <- coxph(as.formula(paste("Surv(DFS_time, DFS_event) ~",
                                paste(clinical, collapse = "+"))),
                data = tr, ties = "breslow", x = TRUE)
  lp1_a <- as.numeric(predict(fit1, newdata = tr, type = "lp"))
  lp1_b <- as.numeric(predict(fit1, newdata = nw, type = "lp"))

  if (length(rad) && !is.null(fit2)) {
    x2 <- as.matrix(tr[, rad, drop = FALSE])
    xv2 <- as.matrix(nw[, rad, drop = FALSE])
    lp2_a <- as.numeric(predict(fit2, newx = x2, s = "lambda.1se", type = "link"))
    lp2_b <- as.numeric(predict(fit2, newx = xv2, s = "lambda.1se", type = "link"))
  } else {
    lp2_a <- rep(0, nrow(tr))
    lp2_b <- rep(0, nrow(nw))
    nz2 <- 0L
  }

  both <- c(clinical, rad)
  x3 <- as.matrix(tr[, both, drop = FALSE])
  xv3 <- as.matrix(nw[, both, drop = FALSE])
  fit3 <- fit_glmnet_cox(x3, y, c(rep(0, length(clinical)), rep(1, length(rad))), inner)
  lp3_a <- as.numeric(predict(fit3, newx = x3, s = "lambda.1se", type = "link"))
  lp3_b <- as.numeric(predict(fit3, newx = xv3, s = "lambda.1se", type = "link"))
  coef3 <- as.numeric(coef(fit3, s = "lambda.1se"))
  nz3 <- if (length(rad)) sum(coef3[-seq_along(clinical)] != 0) else 0L

  pred_rows[[j]] <- data.frame(
    patient_id = c(dat_a$patient_id, dat_b$patient_id),
    dataset = c(rep("A_apparent", nrow(dat_a)), rep("B_external", nrow(dat_b))),
    imputation = j,
    DFS_time = c(dat_a$DFS_time, dat_b$DFS_time),
    DFS_event = c(dat_a$DFS_event, dat_b$DFS_event),
    lp_model1 = c(lp1_a, lp1_b), lp_model2 = c(lp2_a, lp2_b),
    lp_model3 = c(lp3_a, lp3_b)
  )
  complexity[[j]] <- data.frame(imputation = j,
                                 radiomics_after_filter = length(rad),
                                 model2_nonzero = nz2,
                                 model3_radiomics_nonzero = nz3)
}

pred_all <- do.call(rbind, pred_rows)
write.csv(pred_all, file.path(outdir, "full_A_predictions_by_imputation.csv"),
          row.names = FALSE)
write.csv(do.call(rbind, complexity), file.path(outdir, "full_A_model_complexity.csv"),
          row.names = FALSE)

pool_predictions <- function(df) {
  out <- aggregate(df[, c("DFS_time", "DFS_event", "lp_model1", "lp_model2", "lp_model3")],
                   by = list(patient_id = df$patient_id), FUN = mean)
  out$DFS_event <- as.integer(round(out$DFS_event))
  out
}

apparent <- pool_predictions(pred_all)
apparent$dataset <- "A_apparent"
apparent <- apparent[match(dat_a$patient_id, apparent$patient_id), ]

oof <- read.csv(file.path(cv_dir, "oof_predictions.csv"), check.names = FALSE)
oof_pool <- aggregate(oof[, c("lp_model1", "lp_model2", "lp_model3")],
                      by = list(row = oof$row), FUN = mean)
oof_pool$patient_id <- dat_a$patient_id[oof_pool$row]
oof_pool$DFS_time <- dat_a$DFS_time[oof_pool$row]
oof_pool$DFS_event <- dat_a$DFS_event[oof_pool$row]
oof_pool$dataset <- "A_OOF"
oof_pool <- oof_pool[, c("patient_id", "dataset", "DFS_time", "DFS_event",
                         "lp_model1", "lp_model2", "lp_model3")]

b_external <- pool_predictions(pred_all[pred_all$dataset == "B_external", ])
b_external$dataset <- "B_external"
b_external <- b_external[match(dat_b$patient_id, b_external$patient_id), ]

auc_at <- function(df, marker, horizon) {
  if (length(unique(df$DFS_event)) < 2L ||
      sum(df$DFS_event == 1 & df$DFS_time <= horizon) == 0L) {
    return(NA_real_)
  }
  z <- timeROC(T = df$DFS_time, delta = df$DFS_event, marker = df[[marker]],
               cause = 1, weighting = "marginal", times = horizon, iid = FALSE)
  as.numeric(z$AUC[which.min(abs(z$times - horizon))])
}

metric_rows <- list()
for (ds in list(apparent, oof_pool, b_external)) {
  for (h in c(36, 60)) for (model in c("model1", "model2", "model3")) {
    metric_rows[[length(metric_rows) + 1L]] <- data.frame(
      dataset = unique(ds$dataset), model = model,
      horizon_months = h,
      n = nrow(ds), events_total = sum(ds$DFS_event == 1),
      events_by_horizon = sum(ds$DFS_event == 1 & ds$DFS_time <= h),
      at_risk_horizon = sum(ds$DFS_time >= h),
      auc = auc_at(ds, paste0("lp_", model), h)
    )
  }
}
metrics <- do.call(rbind, metric_rows)
write.csv(metrics, file.path(outdir, "quick_check_metrics.csv"), row.names = FALSE)

delta_rows <- do.call(rbind, lapply(split(metrics, metrics$dataset), function(x) {
  do.call(rbind, lapply(c(36, 60), function(h) {
    z <- x[x$horizon_months == h, ]
    a1 <- z$auc[z$model == "model1"]
    a3 <- z$auc[z$model == "model3"]
    data.frame(dataset = unique(x$dataset), horizon_months = h,
               model3_minus_model1_auc = a3 - a1)
  }))
}))
write.csv(delta_rows, file.path(outdir, "model3_minus_model1_auc.csv"), row.names = FALSE)

cohort_rows <- rbind(
  data.frame(dataset = "A", n = nrow(dat_a), events_total = sum(dat_a$DFS_event == 1),
             events_by_36m = sum(dat_a$DFS_event == 1 & dat_a$DFS_time <= 36),
             at_risk_36m = sum(dat_a$DFS_time >= 36),
             events_by_60m = sum(dat_a$DFS_event == 1 & dat_a$DFS_time <= 60),
             at_risk_60m = sum(dat_a$DFS_time >= 60)),
  data.frame(dataset = "B", n = nrow(dat_b), events_total = sum(dat_b$DFS_event == 1),
             events_by_36m = sum(dat_b$DFS_event == 1 & dat_b$DFS_time <= 36),
             at_risk_36m = sum(dat_b$DFS_time >= 36),
             events_by_60m = sum(dat_b$DFS_event == 1 & dat_b$DFS_time <= 60),
             at_risk_60m = sum(dat_b$DFS_time >= 60))
)
write.csv(cohort_rows, file.path(outdir, "cohort_summary.csv"), row.names = FALSE)

a_oof <- metrics[metrics$dataset == "A_OOF", ]
a_app <- metrics[metrics$dataset == "A_apparent", ]
b_auc <- metrics[metrics$dataset == "B_external", ]
warnings <- character()
for (model in c("model1", "model2", "model3")) {
  ap <- a_app$auc[a_app$model == model & a_app$horizon_months == 36]
  oo <- a_oof$auc[a_oof$model == model & a_oof$horizon_months == 36]
  bb <- b_auc$auc[b_auc$model == model & b_auc$horizon_months == 36]
  if (is.finite(oo) && oo <= 0.55) warnings <- c(warnings, paste(model, "A OOF AUC near 0.50"))
  if (is.finite(ap) && is.finite(oo) && ap - oo > 0.05)
    warnings <- c(warnings, paste(model, "apparent minus OOF AUC > 0.05"))
  if (is.finite(ap) && is.finite(oo) && ap - oo > 0.10)
    warnings <- c(warnings, paste(model, "apparent minus OOF AUC > 0.10"))
  if (is.finite(oo) && is.finite(bb) && oo - bb > 0.10)
    warnings <- c(warnings, paste(model, "B AUC is >0.10 below A OOF AUC"))
}
for (ds in unique(delta_rows$dataset)) {
  d <- delta_rows$model3_minus_model1_auc[delta_rows$dataset == ds & delta_rows$horizon_months == 36]
  if (is.finite(d) && d <= 0) warnings <- c(warnings, paste(ds, "Model 3 minus Model 1 AUC <= 0"))
}
if (!length(warnings)) warnings <- "No predefined quick-check warning flag was triggered."

qc_path <- file.path(root, "..", "feature_extract", "output", "qc", "qc_report.csv")
upstream_qc <- character()
if (file.exists(qc_path)) {
  qc <- read.csv(qc_path, check.names = FALSE, fileEncoding = "UTF-8-BOM")
  if ("级别" %in% names(qc) && any(qc[["级别"]] == "ERROR", na.rm = TRUE)) {
    upstream_qc <- paste0("Upstream QC contains ", sum(qc[["级别"]] == "ERROR", na.rm = TRUE),
                          " ERROR record(s); resolve before formal analysis.")
  }
}
if (!length(upstream_qc)) upstream_qc <- "No upstream QC ERROR record was found."

report <- c(
  "# Quick check: three- and five-year DFS AUC",
  "",
  paste0("Generated: ", format(Sys.time(), "%Y-%m-%d %H:%M:%S")),
  "",
  "Full-A Model 1/2/3 were fitted after fold-local imputation, variance filtering, correlation filtering, scaling, and inner 5-fold lambda.1se selection. B outcomes were not used in these steps.",
  "",
  "## Cohort counts",
  "",
  "| Dataset | N | Total events | Events by 36 months | At risk at 36 months | Events by 60 months | At risk at 60 months |",
  "|---|---:|---:|---:|---:|---:|---:|",
  sprintf("| %s | %d | %d | %d | %d | %d | %d |", cohort_rows$dataset, cohort_rows$n,
          cohort_rows$events_total, cohort_rows$events_by_36m, cohort_rows$at_risk_36m,
          cohort_rows$events_by_60m, cohort_rows$at_risk_60m),
  "",
  "## Point estimates",
  "",
  "| Dataset | Model | Horizon | DFS AUC | N | Total events | Events by horizon |",
  "|---|---|---:|---:|---:|---:|---:|",
  sprintf("| %s | %s | %d | %.4f | %d | %d | %d |", metrics$dataset, metrics$model,
          metrics$horizon_months, metrics$auc, metrics$n, metrics$events_total, metrics$events_by_horizon),
  "",
  "## Model 3 minus Model 1",
  "",
  "| Dataset | Horizon | AUC difference |",
  "|---|---:|---:|",
  sprintf("| %s | %d | %.4f |", delta_rows$dataset, delta_rows$horizon_months,
          delta_rows$model3_minus_model1_auc),
  "",
  "## Predefined operational flags",
  "",
  paste0("- ", warnings),
  "",
  "## Upstream QC status",
  "",
  paste0("- ", upstream_qc),
  "",
  "These are point estimates for workflow triage only; no bootstrap confidence intervals, calibration curves, decision-curve analysis, or B-informed tuning were performed."
)
writeLines(report, file.path(outdir, "quick_check_report.md"), useBytes = TRUE)
message("Quick check complete. Outputs: ", outdir)
