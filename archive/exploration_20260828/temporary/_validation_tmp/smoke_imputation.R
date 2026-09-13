source("prognosis_analysis/scripts/03_imputation.R")
set.seed(1)
n <- 60
V_AGE <- "age"
V_MRT <- "mrt_ord"
V_MRN <- "mrn_ord"
V_BIOPSY <- "biopsy_non_adenocarcinoma"
d <- data.frame(rnorm(n, 60, 8), rnorm(n), sample(1:4, n, TRUE),
                sample(0:2, n, TRUE), sample(0:1, n, TRUE), sample(0:1, n, TRUE),
                rnorm(n, 16, 4), rexp(n), sample(0:1, n, TRUE), rexp(n, 0.05),
                sample(0:1, n, TRUE), rnorm(n), rnorm(n), check.names = FALSE)
names(d) <- c(V_AGE, "cea_log", V_MRT, V_MRN, "mrf", "mremvi", "thickness_mm", "eid_mm",
              V_BIOPSY, "DFS_time", "DFS_event", "r1", "r2")
d$cea_log[sample(n, 5)] <- NA
d[[V_BIOPSY]][sample(n, 4)] <- NA
clinical <- c(V_AGE, "cea_log", V_MRT, V_MRN, "mrf", "mremvi", "thickness_mm", "eid_mm", V_BIOPSY)
z <- impute_fold(d[1:45, ], d[46:60, ], clinical, c("r1", "r2"), m = 2, maxit = 2)
stopifnot(!anyNA(z$train[[1]][, c("cea_log", V_BIOPSY)]))
stopifnot(!anyNA(z$newdata[[1]][, c("cea_log", V_BIOPSY)]))
cat("MI toy test OK\n")
