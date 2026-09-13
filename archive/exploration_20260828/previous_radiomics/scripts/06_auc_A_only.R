#!/usr/bin/env Rscript
# A-only time-dependent AUC evaluation for nested-CV predictions.
# This script never reads B outcomes or B predictors.

suppressPackageStartupMessages({
  library(survival)
  library(timeROC)
})

script_arg <- sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE))
script_dir <- dirname(script_arg)
root <- dirname(script_dir)
arg <- commandArgs(trailingOnly = TRUE)
tag <- if (length(arg)) as.character(arg[1]) else "v3_corrected"
cv_dir <- file.path(root, "output", "primary", paste0("nested_cv_", tag))
outdir <- file.path(cv_dir, "auc_A_only")
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)

oof <- read.csv(file.path(cv_dir, "oof_predictions.csv"), check.names = FALSE)
dat <- read.csv(file.path(root, "output", "modeling_v2", "dataset_primary_raw_A_r.csv"),
                check.names = FALSE, fileEncoding = "UTF-8")
models <- c("model1", "model2", "model3")
horizons <- c(36, 60)

auc_at <- function(df, marker, horizon) {
  if (length(unique(df$DFS_event)) < 2L ||
      sum(df$DFS_event == 1 & df$DFS_time <= horizon) == 0L) return(NA_real_)
  z <- timeROC(T = df$DFS_time, delta = df$DFS_event, marker = df[[marker]],
               cause = 1, weighting = "marginal", times = horizon, iid = FALSE)
  as.numeric(z$AUC[which.min(abs(z$times - horizon))])
}

rows <- list()
for (r in sort(unique(oof$repeat_id))) {
  x <- oof[oof$repeat_id == r, , drop = FALSE]
  pooled <- aggregate(x[, paste0("lp_", models), drop = FALSE],
                      by = list(row = x$row), FUN = mean)
  pooled$DFS_time <- dat$DFS_time[pooled$row]
  pooled$DFS_event <- dat$DFS_event[pooled$row]
  for (h in horizons) {
    for (model in models) {
      rows[[length(rows) + 1L]] <- data.frame(
        repeat_id = r, dataset = "A_OOF", model = model,
        horizon_months = h, n = nrow(pooled),
        events_total = sum(pooled$DFS_event == 1),
        events_by_horizon = sum(pooled$DFS_event == 1 & pooled$DFS_time <= h),
        at_risk_horizon = sum(pooled$DFS_time >= h),
        auc = auc_at(pooled, paste0("lp_", model), h))
    }
  }
}
metrics <- do.call(rbind, rows)
write.csv(metrics, file.path(outdir, "A_OOF_auc_by_repeat.csv"), row.names = FALSE)

summary_rows <- list()
for (h in horizons) for (model in models) {
  v <- metrics$auc[metrics$horizon_months == h & metrics$model == model]
  summary_rows[[length(summary_rows) + 1L]] <- data.frame(
    dataset = "A_OOF", model = model, horizon_months = h,
    repeats = sum(is.finite(v)), median_auc = median(v, na.rm = TRUE),
    q1_auc = as.numeric(quantile(v, 0.25, na.rm = TRUE)),
    q3_auc = as.numeric(quantile(v, 0.75, na.rm = TRUE)),
    min_auc = min(v, na.rm = TRUE), max_auc = max(v, na.rm = TRUE))
}
summary <- do.call(rbind, summary_rows)
write.csv(summary, file.path(outdir, "A_OOF_auc_summary.csv"), row.names = FALSE)

delta <- do.call(rbind, lapply(sort(unique(metrics$repeat_id)), function(r) {
  z <- metrics[metrics$repeat_id == r, , drop = FALSE]
  do.call(rbind, lapply(horizons, function(h) {
    a1 <- z$auc[z$horizon_months == h & z$model == "model1"]
    a3 <- z$auc[z$horizon_months == h & z$model == "model3"]
    data.frame(repeat_id = r, horizon_months = h,
               model3_minus_model1_auc = a3 - a1)
  }))
}))
write.csv(delta, file.path(outdir, "model3_minus_model1_auc_by_repeat.csv"), row.names = FALSE)
message("A-only AUC complete. Tag=", tag, "; outputs: ", outdir)
