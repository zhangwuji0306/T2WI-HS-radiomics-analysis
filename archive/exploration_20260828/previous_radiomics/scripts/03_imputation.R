# Fold-local multiple-imputation helpers for the v2 prediction pipeline.
# This file is ASCII-only because the local R runtime starts with a C locale.

suppressPackageStartupMessages({
  library(mice)
  library(survival)
})

V_BIOPSY <- "biopsy_non_adenocarcinoma"

nelson_aalen <- function(time, event) {
  fit <- coxph(Surv(time, event) ~ 1, ties = "breslow")
  bh <- basehaz(fit, centered = FALSE)
  approx(c(0, bh$time), c(0, bh$hazard), xout = time, method = "constant",
         rule = 2, f = 0)$y
}

fit_radiomics_pca <- function(train, newdata, radiomics, n_pc = 10L) {
  x_train <- as.matrix(train[, radiomics, drop = FALSE])
  if (anyNA(x_train)) stop("Radiomics candidates must be complete before imputation")
  n_pc <- min(n_pc, nrow(x_train) - 1L, ncol(x_train))
  fit <- prcomp(x_train, center = TRUE, scale. = TRUE, rank. = n_pc)
  tr <- as.data.frame(predict(fit, x_train)[, seq_len(n_pc), drop = FALSE])
  nw <- as.data.frame(predict(fit, as.matrix(newdata[, radiomics, drop = FALSE]))[
    , seq_len(n_pc), drop = FALSE])
  names(tr) <- names(nw) <- paste0("radPC", seq_len(n_pc))
  list(train = tr, newdata = nw)
}

configure_mice <- function(dat, targets, predictors, include_outcome) {
  method <- rep("", ncol(dat)); names(method) <- names(dat)
  method["cea_log"] <- "pmm"
  method[V_BIOPSY] <- "logreg"
  pred <- matrix(0L, ncol(dat), ncol(dat), dimnames = list(names(dat), names(dat)))
  usable <- intersect(predictors, names(dat))
  if (include_outcome) usable <- union(usable, intersect(c("DFS_event", "NA_DFS"), names(dat)))
  pred[targets, setdiff(usable, targets)] <- 1L
  list(method = method, predictorMatrix = pred)
}

impute_fold <- function(train, newdata, clinical, radiomics, m = 20L, maxit = 20L,
                        seed = 12345L, n_pc = 10L) {
  targets <- c("cea_log", V_BIOPSY)
  stopifnot(all(targets %in% clinical), all(c("DFS_time", "DFS_event") %in% names(train)))
  pcs <- fit_radiomics_pca(train, newdata, radiomics, n_pc)
  base_predictors <- setdiff(clinical, targets)

  # Outcome-assisted imputation is restricted to the outer training fold.
  train_imp_data <- cbind(train[, unique(c(clinical, "DFS_time", "DFS_event")), drop = FALSE],
                          pcs$train)
  train_imp_data[[V_BIOPSY]] <- factor(train_imp_data[[V_BIOPSY]], levels = c(0, 1))
  train_imp_data$NA_DFS <- nelson_aalen(train_imp_data$DFS_time, train_imp_data$DFS_event)
  cfg_train <- configure_mice(train_imp_data, targets,
                              c(base_predictors, names(pcs$train)), include_outcome = TRUE)
  mids_train <- mice(train_imp_data, m = m, maxit = maxit, method = cfg_train$method,
                     predictorMatrix = cfg_train$predictorMatrix, seed = seed,
                     printFlag = FALSE)

  # Deployment-compatible imputation excludes all validation/external outcomes.
  deploy_train <- cbind(train[, clinical, drop = FALSE], pcs$train)
  deploy_new <- cbind(newdata[, clinical, drop = FALSE], pcs$newdata)
  deploy_train[[V_BIOPSY]] <- factor(deploy_train[[V_BIOPSY]], levels = c(0, 1))
  deploy_new[[V_BIOPSY]] <- factor(deploy_new[[V_BIOPSY]], levels = c(0, 1))
  deploy <- rbind(deploy_train, deploy_new)
  ignore <- c(rep(FALSE, nrow(deploy_train)), rep(TRUE, nrow(deploy_new)))
  cfg_new <- configure_mice(deploy, targets, c(base_predictors, names(pcs$train)),
                            include_outcome = FALSE)
  mids_new <- mice(deploy, m = m, maxit = maxit, method = cfg_new$method,
                   predictorMatrix = cfg_new$predictorMatrix, ignore = ignore,
                   seed = seed + 100000L, printFlag = FALSE)

  train_completed <- lapply(seq_len(m), function(i) {
    out <- train
    filled <- complete(mids_train, i)[, targets]
    filled[[V_BIOPSY]] <- as.numeric(as.character(filled[[V_BIOPSY]]))
    out[, targets] <- filled
    out
  })
  new_completed <- lapply(seq_len(m), function(i) {
    out <- newdata
    completed <- complete(mids_new, i)
    idx <- seq.int(nrow(deploy_train) + 1L, nrow(deploy))
    filled <- completed[idx, targets]
    filled[[V_BIOPSY]] <- as.numeric(as.character(filled[[V_BIOPSY]]))
    out[, targets] <- filled
    out
  })
  list(train = train_completed, newdata = new_completed,
       diagnostics = list(train = mids_train, deployment = mids_new))
}
