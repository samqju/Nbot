import os
from pathlib import Path
from dotenv import load_dotenv

# Load the project-local .env before reading runtime settings.
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)

RISK_PER_TRADE_USD = 10.0
RISK_TOLERANCE_PCT = 10.0
MAX_NOTIONAL_USD = 1000.0
NOTIONAL_TOLERANCE_PCT = 1.0
LEVERAGE = 5

# Runtime environment and execution policy are separate controls.
# Expected .env values:
#   TRADING_ENV=TESTNET | LIVE
#   EXECUTION_MODE=SHADOW | TRADE
TRADING_ENV = os.getenv("TRADING_ENV", "TESTNET").strip().upper()
EXECUTION_MODE = os.getenv("EXECUTION_MODE", "SHADOW").strip().upper()

# Backward-compatible derived flag used by the existing engine.
SHADOW_MODE = EXECUTION_MODE == "SHADOW"

# Exchange stop-trigger settlement grace. Binance can remove a triggered
# stop before the position endpoint reflects the resulting close. During
# this short window the engine must wait for settlement instead of treating
# the position as unprotected.
STOP_TRIGGER_GRACE_SECONDS = float(
    os.getenv("STOP_TRIGGER_GRACE_SECONDS", "8")
)
STOP_TRIGGER_POLL_INTERVAL_SECONDS = float(
    os.getenv("STOP_TRIGGER_POLL_INTERVAL_SECONDS", "0.5")
)

# ================================
# PAPER TRADING POLICY
# ================================
#
# SHADOW means local paper execution. Paper state and trade-history files are
# environment-specific so TESTNET+SHADOW and LIVE+SHADOW never share account
# history. Generic PAPER_* overrides remain available for controlled tests.

PAPER_STARTING_BALANCE_USD = float(
    os.getenv("PAPER_STARTING_BALANCE_USD", "10000")
)
PAPER_TAKER_FEE_RATE = float(
    os.getenv("PAPER_TAKER_FEE_RATE", "0.0005")
)
PAPER_ENTRY_SLIPPAGE_PCT = float(
    os.getenv("PAPER_ENTRY_SLIPPAGE_PCT", "0.02")
)
PAPER_EXIT_SLIPPAGE_PCT = float(
    os.getenv("PAPER_EXIT_SLIPPAGE_PCT", "0.02")
)
TESTNET_PAPER_STATE_PATH = os.getenv(
    "TESTNET_PAPER_STATE_PATH",
    "data/paper_state_testnet.json",
).strip()
TESTNET_PAPER_TRADES_PATH = os.getenv(
    "TESTNET_PAPER_TRADES_PATH",
    "data/paper_trades_testnet.jsonl",
).strip()
LIVE_PAPER_STATE_PATH = os.getenv(
    "LIVE_PAPER_STATE_PATH",
    "data/paper_state_live.json",
).strip()
LIVE_PAPER_TRADES_PATH = os.getenv(
    "LIVE_PAPER_TRADES_PATH",
    "data/paper_trades_live.jsonl",
).strip()

_DEFAULT_PAPER_STATE_PATH = (
    TESTNET_PAPER_STATE_PATH
    if TRADING_ENV == "TESTNET"
    else LIVE_PAPER_STATE_PATH
)
_DEFAULT_PAPER_TRADES_PATH = (
    TESTNET_PAPER_TRADES_PATH
    if TRADING_ENV == "TESTNET"
    else LIVE_PAPER_TRADES_PATH
)
PAPER_STATE_PATH = os.getenv(
    "PAPER_STATE_PATH",
    _DEFAULT_PAPER_STATE_PATH,
).strip()
PAPER_TRADES_PATH = os.getenv(
    "PAPER_TRADES_PATH",
    _DEFAULT_PAPER_TRADES_PATH,
).strip()
# Engine and learning-runtime files are environment-specific. This prevents
# TESTNET state, pending simulations, and virtual trades from being restored
# during LIVE+SHADOW operation. Generic overrides remain available for tests.
TESTNET_BOT_STATE_PATH = os.getenv(
    "TESTNET_BOT_STATE_PATH",
    "data/bot_state_testnet.json",
).strip()
LIVE_BOT_STATE_PATH = os.getenv(
    "LIVE_BOT_STATE_PATH",
    "data/bot_state_live.json",
).strip()
TESTNET_CANDIDATE_OBSERVATIONS_PATH = os.getenv(
    "TESTNET_CANDIDATE_OBSERVATIONS_PATH",
    "data/candidate_observations_testnet.jsonl",
).strip()
LIVE_CANDIDATE_OBSERVATIONS_PATH = os.getenv(
    "LIVE_CANDIDATE_OBSERVATIONS_PATH",
    "data/candidate_observations_live.jsonl",
).strip()
TESTNET_CANDIDATE_OUTCOMES_PATH = os.getenv(
    "TESTNET_CANDIDATE_OUTCOMES_PATH",
    "data/candidate_outcomes_testnet.jsonl",
).strip()
LIVE_CANDIDATE_OUTCOMES_PATH = os.getenv(
    "LIVE_CANDIDATE_OUTCOMES_PATH",
    "data/candidate_outcomes_live.jsonl",
).strip()
TESTNET_VIRTUAL_TRADES_PATH = os.getenv(
    "TESTNET_VIRTUAL_TRADES_PATH",
    "data/virtual_trades_testnet.jsonl",
).strip()
LIVE_VIRTUAL_TRADES_PATH = os.getenv(
    "LIVE_VIRTUAL_TRADES_PATH",
    "data/virtual_trades_live.jsonl",
).strip()
TESTNET_LEARNING_RUNTIME_STATE_PATH = os.getenv(
    "TESTNET_LEARNING_RUNTIME_STATE_PATH",
    "data/learning_runtime_state_testnet.json",
).strip()
LIVE_LEARNING_RUNTIME_STATE_PATH = os.getenv(
    "LIVE_LEARNING_RUNTIME_STATE_PATH",
    "data/learning_runtime_state_live.json",
).strip()

_DEFAULT_BOT_STATE_PATH = (
    TESTNET_BOT_STATE_PATH if TRADING_ENV == "TESTNET" else LIVE_BOT_STATE_PATH
)
_DEFAULT_CANDIDATE_OBSERVATIONS_PATH = (
    TESTNET_CANDIDATE_OBSERVATIONS_PATH
    if TRADING_ENV == "TESTNET"
    else LIVE_CANDIDATE_OBSERVATIONS_PATH
)
_DEFAULT_CANDIDATE_OUTCOMES_PATH = (
    TESTNET_CANDIDATE_OUTCOMES_PATH
    if TRADING_ENV == "TESTNET"
    else LIVE_CANDIDATE_OUTCOMES_PATH
)
_DEFAULT_VIRTUAL_TRADES_PATH = (
    TESTNET_VIRTUAL_TRADES_PATH
    if TRADING_ENV == "TESTNET"
    else LIVE_VIRTUAL_TRADES_PATH
)
_DEFAULT_LEARNING_RUNTIME_STATE_PATH = (
    TESTNET_LEARNING_RUNTIME_STATE_PATH
    if TRADING_ENV == "TESTNET"
    else LIVE_LEARNING_RUNTIME_STATE_PATH
)

BOT_STATE_PATH = os.getenv(
    "BOT_STATE_PATH",
    _DEFAULT_BOT_STATE_PATH,
).strip()
CANDIDATE_OBSERVATIONS_PATH = os.getenv(
    "CANDIDATE_OBSERVATIONS_PATH",
    _DEFAULT_CANDIDATE_OBSERVATIONS_PATH,
).strip()
CANDIDATE_OUTCOMES_PATH = os.getenv(
    "CANDIDATE_OUTCOMES_PATH",
    _DEFAULT_CANDIDATE_OUTCOMES_PATH,
).strip()
VIRTUAL_TRADES_PATH = os.getenv(
    "VIRTUAL_TRADES_PATH",
    _DEFAULT_VIRTUAL_TRADES_PATH,
).strip()
LEARNING_RUNTIME_STATE_PATH = os.getenv(
    "LEARNING_RUNTIME_STATE_PATH",
    _DEFAULT_LEARNING_RUNTIME_STATE_PATH,
).strip()
TRAINING_DATASET_PATH = os.getenv(
    "TRAINING_DATASET_PATH",
    "data/training_dataset.jsonl",
).strip()
DATASET_INTEGRITY_REPORT_PATH = os.getenv(
    "DATASET_INTEGRITY_REPORT_PATH",
    "data/dataset_integrity_report.json",
).strip()
TRAIN_SPLIT_PATH = os.getenv(
    "TRAIN_SPLIT_PATH",
    "data/training_split_train.jsonl",
).strip()
VALIDATION_SPLIT_PATH = os.getenv(
    "VALIDATION_SPLIT_PATH",
    "data/training_split_validation.jsonl",
).strip()
TEST_SPLIT_PATH = os.getenv(
    "TEST_SPLIT_PATH",
    "data/training_split_test.jsonl",
).strip()
TIME_SPLIT_REPORT_PATH = os.getenv(
    "TIME_SPLIT_REPORT_PATH",
    "data/time_split_report.json",
).strip()
BASELINE_MODEL_ARTIFACT_PATH = os.getenv(
    "BASELINE_MODEL_ARTIFACT_PATH",
    "models/baseline_candidate_model.pkl",
).strip()
BASELINE_MODEL_REPORT_PATH = os.getenv(
    "BASELINE_MODEL_REPORT_PATH",
    "data/baseline_model_report.json",
).strip()
BASELINE_MODEL_OUTCOME_TYPE = os.getenv(
    "BASELINE_MODEL_OUTCOME_TYPE",
    "VIRTUAL_TRADE",
).strip().upper()
BASELINE_MODEL_MIN_TRAIN_ROWS = int(
    os.getenv("BASELINE_MODEL_MIN_TRAIN_ROWS", "100")
)
BASELINE_MODEL_MIN_EVAL_ROWS = int(
    os.getenv("BASELINE_MODEL_MIN_EVAL_ROWS", "20")
)
BASELINE_MODEL_RANDOM_STATE = int(
    os.getenv("BASELINE_MODEL_RANDOM_STATE", "42")
)
MODEL_EVALUATION_REPORT_PATH = os.getenv(
    "MODEL_EVALUATION_REPORT_PATH",
    "data/model_evaluation_report.json",
).strip()
MODEL_CALIBRATION_REPORT_PATH = os.getenv(
    "MODEL_CALIBRATION_REPORT_PATH",
    "data/model_calibration_report.json",
).strip()
MODEL_EVALUATION_MIN_SUBGROUP_ROWS = int(
    os.getenv("MODEL_EVALUATION_MIN_SUBGROUP_ROWS", "20")
)
MODEL_EVALUATION_CALIBRATION_BINS = int(
    os.getenv("MODEL_EVALUATION_CALIBRATION_BINS", "10")
)
MODEL_EVALUATION_DRIFT_BINS = int(
    os.getenv("MODEL_EVALUATION_DRIFT_BINS", "10")
)
ENSEMBLE_EXPERIMENT_ARTIFACT_PATH = os.getenv(
    "ENSEMBLE_EXPERIMENT_ARTIFACT_PATH",
    "models/ensemble_experiment.pkl",
).strip()
ENSEMBLE_EXPERIMENT_REPORT_PATH = os.getenv(
    "ENSEMBLE_EXPERIMENT_REPORT_PATH",
    "data/ensemble_experiment_report.json",
).strip()
ENSEMBLE_EXPERIMENT_MIN_TRAIN_ROWS = int(
    os.getenv("ENSEMBLE_EXPERIMENT_MIN_TRAIN_ROWS", "200")
)
ENSEMBLE_EXPERIMENT_MIN_EVAL_ROWS = int(
    os.getenv("ENSEMBLE_EXPERIMENT_MIN_EVAL_ROWS", "40")
)
ENSEMBLE_EXPERIMENT_RANDOM_STATE = int(
    os.getenv("ENSEMBLE_EXPERIMENT_RANDOM_STATE", "42")
)
ENSEMBLE_EXPERIMENT_OUTCOME_TYPE = os.getenv(
    "ENSEMBLE_EXPERIMENT_OUTCOME_TYPE",
    "VIRTUAL_TRADE",
).strip().upper()
SHADOW_MODEL_SCORING_ENABLED = (
    os.getenv("SHADOW_MODEL_SCORING_ENABLED", "false")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)
SHADOW_MODEL_ARTIFACT_PATH = os.getenv(
    "SHADOW_MODEL_ARTIFACT_PATH",
    ENSEMBLE_EXPERIMENT_ARTIFACT_PATH,
).strip()
SHADOW_MODEL_PREDICTIONS_PATH = os.getenv(
    "SHADOW_MODEL_PREDICTIONS_PATH",
    "data/shadow_model_predictions.jsonl",
).strip()
SHADOW_MODEL_REFRESH_SECONDS = int(
    os.getenv("SHADOW_MODEL_REFRESH_SECONDS", "300")
)
SHADOW_PROMOTION_REPORT_PATH = os.getenv(
    "SHADOW_PROMOTION_REPORT_PATH",
    "data/shadow_promotion_report.json",
).strip()
SHADOW_PROMOTION_OUTCOME_TYPE = os.getenv(
    "SHADOW_PROMOTION_OUTCOME_TYPE",
    "VIRTUAL_TRADE",
).strip().upper()
SHADOW_PROMOTION_MIN_MATCHED_CANDIDATES = int(
    os.getenv("SHADOW_PROMOTION_MIN_MATCHED_CANDIDATES", "200")
)
SHADOW_PROMOTION_MIN_PAIRED_BATCHES = int(
    os.getenv("SHADOW_PROMOTION_MIN_PAIRED_BATCHES", "50")
)
SHADOW_PROMOTION_MIN_AVG_R_LIFT = float(
    os.getenv("SHADOW_PROMOTION_MIN_AVG_R_LIFT", "0.10")
)
SHADOW_PROMOTION_MAX_WIN_RATE_DROP = float(
    os.getenv("SHADOW_PROMOTION_MAX_WIN_RATE_DROP", "0.02")
)
SHADOW_PROMOTION_MAX_BRIER_SCORE = float(
    os.getenv("SHADOW_PROMOTION_MAX_BRIER_SCORE", "0.25")
)
SHADOW_PROMOTION_MAX_CALIBRATION_GAP = float(
    os.getenv("SHADOW_PROMOTION_MAX_CALIBRATION_GAP", "0.10")
)
SHADOW_PROMOTION_MAX_FEATURE_PSI = float(
    os.getenv("SHADOW_PROMOTION_MAX_FEATURE_PSI", "0.25")
)
TIME_SPLIT_TRAIN_RATIO = float(
    os.getenv("TIME_SPLIT_TRAIN_RATIO", "0.70")
)
TIME_SPLIT_VALIDATION_RATIO = float(
    os.getenv("TIME_SPLIT_VALIDATION_RATIO", "0.15")
)
TIME_SPLIT_TEST_RATIO = float(
    os.getenv("TIME_SPLIT_TEST_RATIO", "0.15")
)
TIME_SPLIT_EMBARGO_SECONDS = int(
    os.getenv("TIME_SPLIT_EMBARGO_SECONDS", "3600")
)
VIRTUAL_TRADE_TARGET_R = float(
    os.getenv("VIRTUAL_TRADE_TARGET_R", "2.0")
)
VIRTUAL_TRADE_MAX_CANDLES = int(
    os.getenv("VIRTUAL_TRADE_MAX_CANDLES", "24")
)
VIRTUAL_TRADE_MAX_ACTIVE = int(
    os.getenv("VIRTUAL_TRADE_MAX_ACTIVE", "500")
)
OBSERVATION_UNIVERSE_SIZE = int(
    os.getenv("OBSERVATION_UNIVERSE_SIZE", "200")
)
OBSERVATION_UNIVERSE_CORE_SIZE = int(
    os.getenv("OBSERVATION_UNIVERSE_CORE_SIZE", "150")
)
OBSERVATION_UNIVERSE_MIN_QUOTE_VOLUME = float(
    os.getenv("OBSERVATION_UNIVERSE_MIN_QUOTE_VOLUME", "3000000")
)
OBSERVATION_UNIVERSE_MAX_SPREAD_PCT = float(
    os.getenv("OBSERVATION_UNIVERSE_MAX_SPREAD_PCT", "0.50")
)
OBSERVATION_UNIVERSE_REFRESH_SECONDS = int(
    os.getenv("OBSERVATION_UNIVERSE_REFRESH_SECONDS", "1800")
)
STRUCTURE_UNIVERSE_ENABLED = (
    os.getenv("STRUCTURE_UNIVERSE_ENABLED", "true")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)
STRUCTURE_UNIVERSE_SIZE = int(
    os.getenv("STRUCTURE_UNIVERSE_SIZE", "30")
)
STRUCTURE_UNIVERSE_PREFILTER_SIZE = int(
    os.getenv("STRUCTURE_UNIVERSE_PREFILTER_SIZE", "80")
)
STRUCTURE_UNIVERSE_CANDLE_LIMIT = int(
    os.getenv("STRUCTURE_UNIVERSE_CANDLE_LIMIT", "121")
)
STRUCTURE_UNIVERSE_MIN_COMPLETED_CANDLES = int(
    os.getenv("STRUCTURE_UNIVERSE_MIN_COMPLETED_CANDLES", "60")
)
STRUCTURE_UNIVERSE_MIN_QUOTE_VOLUME = float(
    os.getenv("STRUCTURE_UNIVERSE_MIN_QUOTE_VOLUME", "15000000")
)
STRUCTURE_UNIVERSE_MIN_CHANGE_PCT = float(
    os.getenv("STRUCTURE_UNIVERSE_MIN_CHANGE_PCT", "0.50")
)
STRUCTURE_UNIVERSE_MAX_CHANGE_PCT = float(
    os.getenv("STRUCTURE_UNIVERSE_MAX_CHANGE_PCT", "30.0")
)
STRUCTURE_UNIVERSE_MAX_WORKERS = int(
    os.getenv("STRUCTURE_UNIVERSE_MAX_WORKERS", "6")
)
STRUCTURE_UNIVERSE_RETENTION_BONUS = float(
    os.getenv("STRUCTURE_UNIVERSE_RETENTION_BONUS", "0.03")
)
STRUCTURE_UNIVERSE_MIN_SCORE = float(
    os.getenv("STRUCTURE_UNIVERSE_MIN_SCORE", "0.35")
)
STRUCTURE_UNIVERSE_MAX_TREND = int(
    os.getenv("STRUCTURE_UNIVERSE_MAX_TREND", "12")
)
STRUCTURE_UNIVERSE_MAX_BREAKOUT = int(
    os.getenv("STRUCTURE_UNIVERSE_MAX_BREAKOUT", "10")
)
STRUCTURE_UNIVERSE_MAX_REVERSION = int(
    os.getenv("STRUCTURE_UNIVERSE_MAX_REVERSION", "8")
)
# Universe networking and snapshots are isolated by TRADING_ENV.
_ACTIVE_UNIVERSE_BASE_URL_DEFAULT = os.getenv(
    f"{TRADING_ENV}_BASE_URL",
    "",
).strip()
STRUCTURE_UNIVERSE_MARKET_BASE_URL = os.getenv(
    f"{TRADING_ENV}_UNIVERSE_MARKET_BASE_URL",
    os.getenv(
        "STRUCTURE_UNIVERSE_MARKET_BASE_URL",
        _ACTIVE_UNIVERSE_BASE_URL_DEFAULT,
    ),
).strip()
OBSERVATION_UNIVERSE_MARKET_BASE_URL = os.getenv(
    f"{TRADING_ENV}_OBSERVATION_UNIVERSE_MARKET_BASE_URL",
    os.getenv(
        "OBSERVATION_UNIVERSE_MARKET_BASE_URL",
        _ACTIVE_UNIVERSE_BASE_URL_DEFAULT,
    ),
).strip()
UNIVERSE_SNAPSHOT_PATH = os.getenv(
    f"{TRADING_ENV}_UNIVERSE_SNAPSHOT_PATH",
    f"data/universe_{TRADING_ENV.lower()}.json",
).strip()
OBSERVATION_UNIVERSE_SNAPSHOT_PATH = os.getenv(
    f"{TRADING_ENV}_OBSERVATION_UNIVERSE_SNAPSHOT_PATH",
    f"data/observation_universe_{TRADING_ENV.lower()}.json",
).strip()
del _ACTIVE_UNIVERSE_BASE_URL_DEFAULT
CANDIDATE_SCORE_RULE_WEIGHT = float(os.getenv("CANDIDATE_SCORE_RULE_WEIGHT", "0.50"))
CANDIDATE_SCORE_TREND_WEIGHT = float(os.getenv("CANDIDATE_SCORE_TREND_WEIGHT", "0.20"))
CANDIDATE_SCORE_VOLATILITY_WEIGHT = float(os.getenv("CANDIDATE_SCORE_VOLATILITY_WEIGHT", "0.10"))
CANDIDATE_SCORE_CANDLE_WEIGHT = float(os.getenv("CANDIDATE_SCORE_CANDLE_WEIGHT", "0.05"))
CANDIDATE_SCORE_LOCATION_WEIGHT = float(os.getenv("CANDIDATE_SCORE_LOCATION_WEIGHT", "0.10"))
CANDIDATE_SCORE_CONSISTENCY_WEIGHT = float(os.getenv("CANDIDATE_SCORE_CONSISTENCY_WEIGHT", "0.05"))
CANDIDATE_RISK_MIN_STOP_PCT = float(os.getenv("CANDIDATE_RISK_MIN_STOP_PCT", "0.50"))
CANDIDATE_RISK_MAX_STOP_PCT = float(os.getenv("CANDIDATE_RISK_MAX_STOP_PCT", "2.00"))
CANDIDATE_RISK_RANGE_MULTIPLIER = float(os.getenv("CANDIDATE_RISK_RANGE_MULTIPLIER", "1.00"))
PAPER_HEARTBEAT_INTERVAL_SECONDS = float(
    os.getenv("PAPER_HEARTBEAT_INTERVAL_SECONDS", "60")
)
PAPER_PREFLIGHT_SYMBOL = os.getenv(
    "PAPER_PREFLIGHT_SYMBOL",
    "BTCUSDT",
).strip().upper()
PAPER_PREFLIGHT_CANDLE_LIMIT = int(
    os.getenv("PAPER_PREFLIGHT_CANDLE_LIMIT", "5")
)
PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS = float(
    os.getenv("PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS", "10")
)
PAPER_REST_POLL_INTERVAL_SECONDS = float(
    os.getenv("PAPER_REST_POLL_INTERVAL_SECONDS", "2")
)
PAPER_WS_RETRY_INTERVAL_SECONDS = float(
    os.getenv("PAPER_WS_RETRY_INTERVAL_SECONDS", "300")
)

# Temporary Phase 1 execution-smoke strategy. PAPER_TEST is deliberately
# restricted to SHADOW mode and must never submit exchange orders.
STRATEGY_MODE = os.getenv("STRATEGY_MODE", "STRUCTURE").strip().upper()
PAPER_TEST_MIN_MOVE_PCT = float(
    os.getenv("PAPER_TEST_MIN_MOVE_PCT", "0.10")
)
PAPER_TEST_COOLDOWN_CANDLES = int(
    os.getenv("PAPER_TEST_COOLDOWN_CANDLES", "6")
)

# A second, explicit gate for future real-money execution. Keeping this
# disabled has no effect on TESTNET + TRADE or either SHADOW combination.
LIVE_TRADING_CONFIRMATION = os.getenv(
    "LIVE_TRADING_CONFIRMATION",
    "DISABLED",
).strip()
TESTNET_TRADING_CONFIRMATION = os.getenv(
    "TESTNET_TRADING_CONFIRMATION",
    "DISABLED",
).strip()
TESTNET_TRADING_ARM_FILE = os.getenv(
    "TESTNET_TRADING_ARM_FILE",
    "runtime/TESTNET_TRADING_ARMED",
).strip()
TESTNET_MAX_SESSION_ENTRIES = int(
    os.getenv("TESTNET_MAX_SESSION_ENTRIES", "5")
)
TESTNET_MAX_ENTRY_NOTIONAL_USD = float(
    os.getenv("TESTNET_MAX_ENTRY_NOTIONAL_USD", "1000")
)
TESTNET_REQUIRE_FLAT_START = (
    os.getenv("TESTNET_REQUIRE_FLAT_START", "true")
    .strip()
    .lower()
    in {"1", "true", "yes", "on"}
)
_REQUIRED_LIVE_TRADING_CONFIRMATION = "I_ACCEPT_REAL_MONEY_EXECUTION"
_REQUIRED_TESTNET_TRADING_CONFIRMATION = "I_ACCEPT_TESTNET_ORDER_EXECUTION"

# Phase 2.5 final capability gate. Real order writes remain unavailable.
LIVE_ADAPTER_MODE = os.getenv(
    "LIVE_ADAPTER_MODE",
    "READ_ONLY",
).strip().upper()
LIVE_ORDER_WRITES_ENABLED = os.getenv(
    "LIVE_ORDER_WRITES_ENABLED",
    "false",
).strip().lower() in {"1", "true", "yes", "on"}
LIVE_TRADING_ARM_FILE = os.getenv(
    "LIVE_TRADING_ARM_FILE",
    "data/live_trading.arm",
).strip()
LIVE_SNAPSHOT_PATH = os.getenv(
    "LIVE_SNAPSHOT_PATH",
    "data/live_snapshot.json",
).strip()

# ================================
# ORDER EXECUTION POLICY
# ================================

ENTRY_SLIPPAGE_PCT = 1.0
MAX_SPREAD_PCT = 0.25

# ================================
# SYSTEM HALT POLICY
# ================================

HALT_ON_RISK_BREACH = True


# ==========================================================
# CONFIG VALIDATION (IMPORT-TIME GUARD)
# ==========================================================

def _validate():
    if STOP_TRIGGER_GRACE_SECONDS < 0:
        raise ValueError("CONFIG_INVALID: STOP_TRIGGER_GRACE_SECONDS")
    if STOP_TRIGGER_POLL_INTERVAL_SECONDS <= 0:
        raise ValueError("CONFIG_INVALID: STOP_TRIGGER_POLL_INTERVAL_SECONDS")
    if RISK_PER_TRADE_USD <= 0:
        raise ValueError("CONFIG_INVALID: RISK_PER_TRADE_USD")

    if not (0 <= RISK_TOLERANCE_PCT <= 20):
        raise ValueError("CONFIG_INVALID: RISK_TOLERANCE_PCT")

    if MAX_NOTIONAL_USD <= 0:
        raise ValueError("CONFIG_INVALID: MAX_NOTIONAL_USD")

    if not (0 <= NOTIONAL_TOLERANCE_PCT <= 5):
        raise ValueError("CONFIG_INVALID: NOTIONAL_TOLERANCE_PCT")

    if LEVERAGE <= 0:
        raise ValueError("CONFIG_INVALID: LEVERAGE")

    if not (0 <= ENTRY_SLIPPAGE_PCT <= 10):
        raise ValueError("CONFIG_INVALID: ENTRY_SLIPPAGE_PCT")

    if TRADING_ENV not in {"TESTNET", "LIVE"}:
        raise ValueError("CONFIG_INVALID: TRADING_ENV")

    if EXECUTION_MODE not in {"SHADOW", "TRADE"}:
        raise ValueError("CONFIG_INVALID: EXECUTION_MODE")

    if not isinstance(SHADOW_MODE, bool):
        raise ValueError("CONFIG_INVALID: SHADOW_MODE")

    if PAPER_STARTING_BALANCE_USD <= 0:
        raise ValueError("CONFIG_INVALID: PAPER_STARTING_BALANCE_USD")

    if not (0 <= PAPER_TAKER_FEE_RATE <= 0.01):
        raise ValueError("CONFIG_INVALID: PAPER_TAKER_FEE_RATE")

    if not (0 <= PAPER_ENTRY_SLIPPAGE_PCT <= 5):
        raise ValueError("CONFIG_INVALID: PAPER_ENTRY_SLIPPAGE_PCT")

    if not (0 <= PAPER_EXIT_SLIPPAGE_PCT <= 5):
        raise ValueError("CONFIG_INVALID: PAPER_EXIT_SLIPPAGE_PCT")

    if not PAPER_STATE_PATH:
        raise ValueError("CONFIG_INVALID: PAPER_STATE_PATH")

    if not PAPER_TRADES_PATH:
        raise ValueError("CONFIG_INVALID: PAPER_TRADES_PATH")

    if PAPER_STATE_PATH == PAPER_TRADES_PATH:
        raise ValueError("CONFIG_INVALID: PAPER_PATHS_MUST_DIFFER")

    if not BOT_STATE_PATH:
        raise ValueError("CONFIG_INVALID: BOT_STATE_PATH")

    if BOT_STATE_PATH in {PAPER_STATE_PATH, PAPER_TRADES_PATH}:
        raise ValueError("CONFIG_INVALID: BOT_STATE_PATH_CONFLICT")

    if not CANDIDATE_OBSERVATIONS_PATH:
        raise ValueError("CONFIG_INVALID: CANDIDATE_OBSERVATIONS_PATH")

    if CANDIDATE_OBSERVATIONS_PATH in {
        PAPER_STATE_PATH,
        PAPER_TRADES_PATH,
        BOT_STATE_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: CANDIDATE_OBSERVATIONS_PATH_CONFLICT"
        )

    if not CANDIDATE_OUTCOMES_PATH:
        raise ValueError("CONFIG_INVALID: CANDIDATE_OUTCOMES_PATH")

    if CANDIDATE_OUTCOMES_PATH in {
        PAPER_STATE_PATH,
        PAPER_TRADES_PATH,
        CANDIDATE_OBSERVATIONS_PATH,
        BOT_STATE_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: CANDIDATE_OUTCOMES_PATH_CONFLICT"
        )

    if not VIRTUAL_TRADES_PATH:
        raise ValueError("CONFIG_INVALID: VIRTUAL_TRADES_PATH")
    if VIRTUAL_TRADES_PATH in {
        PAPER_STATE_PATH,
        PAPER_TRADES_PATH,
        CANDIDATE_OBSERVATIONS_PATH,
        CANDIDATE_OUTCOMES_PATH,
        BOT_STATE_PATH,
    }:
        raise ValueError("CONFIG_INVALID: VIRTUAL_TRADES_PATH_CONFLICT")

    if not LEARNING_RUNTIME_STATE_PATH:
        raise ValueError(
            "CONFIG_INVALID: LEARNING_RUNTIME_STATE_PATH"
        )
    if LEARNING_RUNTIME_STATE_PATH in {
        PAPER_STATE_PATH,
        PAPER_TRADES_PATH,
        CANDIDATE_OBSERVATIONS_PATH,
        CANDIDATE_OUTCOMES_PATH,
        VIRTUAL_TRADES_PATH,
        BOT_STATE_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: LEARNING_RUNTIME_STATE_PATH_CONFLICT"
        )

    if not TRAINING_DATASET_PATH:
        raise ValueError("CONFIG_INVALID: TRAINING_DATASET_PATH")
    if not DATASET_INTEGRITY_REPORT_PATH:
        raise ValueError(
            "CONFIG_INVALID: DATASET_INTEGRITY_REPORT_PATH"
        )

    learning_paths = {
        PAPER_STATE_PATH,
        PAPER_TRADES_PATH,
        BOT_STATE_PATH,
        CANDIDATE_OBSERVATIONS_PATH,
        CANDIDATE_OUTCOMES_PATH,
        VIRTUAL_TRADES_PATH,
        LEARNING_RUNTIME_STATE_PATH,
        TRAINING_DATASET_PATH,
        DATASET_INTEGRITY_REPORT_PATH,
    }
    if len(learning_paths) != 9:
        raise ValueError(
            "CONFIG_INVALID: LEARNING_DATA_PATH_CONFLICT"
        )

    split_paths = {
        TRAIN_SPLIT_PATH,
        VALIDATION_SPLIT_PATH,
        TEST_SPLIT_PATH,
        TIME_SPLIT_REPORT_PATH,
    }
    if any(not path for path in split_paths):
        raise ValueError("CONFIG_INVALID: TIME_SPLIT_PATH")
    if learning_paths & split_paths:
        raise ValueError(
            "CONFIG_INVALID: TIME_SPLIT_PATH_CONFLICT"
        )
    if len(split_paths) != 4:
        raise ValueError(
            "CONFIG_INVALID: TIME_SPLIT_PATH_DUPLICATE"
        )

    split_ratios = (
        TIME_SPLIT_TRAIN_RATIO,
        TIME_SPLIT_VALIDATION_RATIO,
        TIME_SPLIT_TEST_RATIO,
    )
    if any(ratio <= 0 or ratio >= 1 for ratio in split_ratios):
        raise ValueError("CONFIG_INVALID: TIME_SPLIT_RATIO_RANGE")
    if abs(sum(split_ratios) - 1.0) > 1e-9:
        raise ValueError("CONFIG_INVALID: TIME_SPLIT_RATIO_SUM")
    if not (0 <= TIME_SPLIT_EMBARGO_SECONDS <= 604800):
        raise ValueError(
            "CONFIG_INVALID: TIME_SPLIT_EMBARGO_SECONDS"
        )

    if not BASELINE_MODEL_ARTIFACT_PATH:
        raise ValueError(
            "CONFIG_INVALID: BASELINE_MODEL_ARTIFACT_PATH"
        )
    if not BASELINE_MODEL_REPORT_PATH:
        raise ValueError(
            "CONFIG_INVALID: BASELINE_MODEL_REPORT_PATH"
        )
    if BASELINE_MODEL_ARTIFACT_PATH == BASELINE_MODEL_REPORT_PATH:
        raise ValueError(
            "CONFIG_INVALID: BASELINE_MODEL_PATH_CONFLICT"
        )
    if BASELINE_MODEL_OUTCOME_TYPE not in {
        "VIRTUAL_TRADE",
        "FORWARD_5_CANDLE",
        "EXECUTED_TRADE",
    }:
        raise ValueError(
            "CONFIG_INVALID: BASELINE_MODEL_OUTCOME_TYPE"
        )
    if BASELINE_MODEL_MIN_TRAIN_ROWS < 20:
        raise ValueError(
            "CONFIG_INVALID: BASELINE_MODEL_MIN_TRAIN_ROWS"
        )
    if BASELINE_MODEL_MIN_EVAL_ROWS < 5:
        raise ValueError(
            "CONFIG_INVALID: BASELINE_MODEL_MIN_EVAL_ROWS"
        )

    if not MODEL_EVALUATION_REPORT_PATH:
        raise ValueError(
            "CONFIG_INVALID: MODEL_EVALUATION_REPORT_PATH"
        )
    if not MODEL_CALIBRATION_REPORT_PATH:
        raise ValueError(
            "CONFIG_INVALID: MODEL_CALIBRATION_REPORT_PATH"
        )
    if MODEL_EVALUATION_REPORT_PATH in {
        BASELINE_MODEL_ARTIFACT_PATH,
        BASELINE_MODEL_REPORT_PATH,
        MODEL_CALIBRATION_REPORT_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: MODEL_EVALUATION_PATH_CONFLICT"
        )
    if MODEL_CALIBRATION_REPORT_PATH in {
        BASELINE_MODEL_ARTIFACT_PATH,
        BASELINE_MODEL_REPORT_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: MODEL_CALIBRATION_PATH_CONFLICT"
        )
    if MODEL_EVALUATION_MIN_SUBGROUP_ROWS < 5:
        raise ValueError(
            "CONFIG_INVALID: MODEL_EVALUATION_MIN_SUBGROUP_ROWS"
        )
    if not (5 <= MODEL_EVALUATION_CALIBRATION_BINS <= 50):
        raise ValueError(
            "CONFIG_INVALID: MODEL_EVALUATION_CALIBRATION_BINS"
        )
    if not (5 <= MODEL_EVALUATION_DRIFT_BINS <= 50):
        raise ValueError(
            "CONFIG_INVALID: MODEL_EVALUATION_DRIFT_BINS"
        )

    if not ENSEMBLE_EXPERIMENT_ARTIFACT_PATH:
        raise ValueError(
            "CONFIG_INVALID: ENSEMBLE_EXPERIMENT_ARTIFACT_PATH"
        )
    if not ENSEMBLE_EXPERIMENT_REPORT_PATH:
        raise ValueError(
            "CONFIG_INVALID: ENSEMBLE_EXPERIMENT_REPORT_PATH"
        )
    if ENSEMBLE_EXPERIMENT_ARTIFACT_PATH in {
        BASELINE_MODEL_ARTIFACT_PATH,
        BASELINE_MODEL_REPORT_PATH,
        MODEL_EVALUATION_REPORT_PATH,
        MODEL_CALIBRATION_REPORT_PATH,
        ENSEMBLE_EXPERIMENT_REPORT_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: ENSEMBLE_EXPERIMENT_ARTIFACT_CONFLICT"
        )
    if ENSEMBLE_EXPERIMENT_REPORT_PATH in {
        BASELINE_MODEL_ARTIFACT_PATH,
        BASELINE_MODEL_REPORT_PATH,
        MODEL_EVALUATION_REPORT_PATH,
        MODEL_CALIBRATION_REPORT_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: ENSEMBLE_EXPERIMENT_REPORT_CONFLICT"
        )
    if ENSEMBLE_EXPERIMENT_MIN_TRAIN_ROWS < 50:
        raise ValueError(
            "CONFIG_INVALID: ENSEMBLE_EXPERIMENT_MIN_TRAIN_ROWS"
        )
    if ENSEMBLE_EXPERIMENT_MIN_EVAL_ROWS < 10:
        raise ValueError(
            "CONFIG_INVALID: ENSEMBLE_EXPERIMENT_MIN_EVAL_ROWS"
        )
    if not ENSEMBLE_EXPERIMENT_OUTCOME_TYPE:
        raise ValueError(
            "CONFIG_INVALID: ENSEMBLE_EXPERIMENT_OUTCOME_TYPE"
        )

    if not SHADOW_MODEL_ARTIFACT_PATH:
        raise ValueError(
            "CONFIG_INVALID: SHADOW_MODEL_ARTIFACT_PATH"
        )
    if not SHADOW_MODEL_PREDICTIONS_PATH:
        raise ValueError(
            "CONFIG_INVALID: SHADOW_MODEL_PREDICTIONS_PATH"
        )
    if SHADOW_MODEL_PREDICTIONS_PATH in {
        SHADOW_MODEL_ARTIFACT_PATH,
        ENSEMBLE_EXPERIMENT_REPORT_PATH,
        BASELINE_MODEL_REPORT_PATH,
        MODEL_EVALUATION_REPORT_PATH,
        MODEL_CALIBRATION_REPORT_PATH,
        CANDIDATE_OBSERVATIONS_PATH,
        CANDIDATE_OUTCOMES_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: SHADOW_MODEL_PREDICTIONS_PATH_CONFLICT"
        )
    if not (30 <= SHADOW_MODEL_REFRESH_SECONDS <= 86400):
        raise ValueError(
            "CONFIG_INVALID: SHADOW_MODEL_REFRESH_SECONDS"
        )

    if not SHADOW_PROMOTION_REPORT_PATH:
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_REPORT_PATH"
        )
    if SHADOW_PROMOTION_REPORT_PATH in {
        SHADOW_MODEL_PREDICTIONS_PATH,
        CANDIDATE_OUTCOMES_PATH,
        MODEL_EVALUATION_REPORT_PATH,
        MODEL_CALIBRATION_REPORT_PATH,
        ENSEMBLE_EXPERIMENT_REPORT_PATH,
    }:
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_REPORT_PATH_CONFLICT"
        )
    if not SHADOW_PROMOTION_OUTCOME_TYPE:
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_OUTCOME_TYPE"
        )
    if SHADOW_PROMOTION_MIN_MATCHED_CANDIDATES < 20:
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_MIN_MATCHED_CANDIDATES"
        )
    if SHADOW_PROMOTION_MIN_PAIRED_BATCHES < 10:
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_MIN_PAIRED_BATCHES"
        )
    if SHADOW_PROMOTION_MIN_PAIRED_BATCHES > (
        SHADOW_PROMOTION_MIN_MATCHED_CANDIDATES
    ):
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_SAMPLE_RELATION"
        )
    if not (0 <= SHADOW_PROMOTION_MIN_AVG_R_LIFT <= 5):
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_MIN_AVG_R_LIFT"
        )
    if not (0 <= SHADOW_PROMOTION_MAX_WIN_RATE_DROP <= 0.50):
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_MAX_WIN_RATE_DROP"
        )
    if not (0 < SHADOW_PROMOTION_MAX_BRIER_SCORE <= 1):
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_MAX_BRIER_SCORE"
        )
    if not (0 <= SHADOW_PROMOTION_MAX_CALIBRATION_GAP <= 1):
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_MAX_CALIBRATION_GAP"
        )
    if not (0 <= SHADOW_PROMOTION_MAX_FEATURE_PSI <= 10):
        raise ValueError(
            "CONFIG_INVALID: SHADOW_PROMOTION_MAX_FEATURE_PSI"
        )
    if not (0.25 <= VIRTUAL_TRADE_TARGET_R <= 10):
        raise ValueError("CONFIG_INVALID: VIRTUAL_TRADE_TARGET_R")
    if not (3 <= VIRTUAL_TRADE_MAX_CANDLES <= 500):
        raise ValueError("CONFIG_INVALID: VIRTUAL_TRADE_MAX_CANDLES")
    if not (10 <= VIRTUAL_TRADE_MAX_ACTIVE <= 10000):
        raise ValueError("CONFIG_INVALID: VIRTUAL_TRADE_MAX_ACTIVE")

    if not (30 <= OBSERVATION_UNIVERSE_SIZE <= 500):
        raise ValueError("CONFIG_INVALID: OBSERVATION_UNIVERSE_SIZE")
    if not (
        30 <= OBSERVATION_UNIVERSE_CORE_SIZE
        <= OBSERVATION_UNIVERSE_SIZE
    ):
        raise ValueError(
            "CONFIG_INVALID: OBSERVATION_UNIVERSE_CORE_SIZE"
        )
    if OBSERVATION_UNIVERSE_MIN_QUOTE_VOLUME <= 0:
        raise ValueError(
            "CONFIG_INVALID: OBSERVATION_UNIVERSE_MIN_QUOTE_VOLUME"
        )
    if not (0.01 <= OBSERVATION_UNIVERSE_MAX_SPREAD_PCT <= 5):
        raise ValueError(
            "CONFIG_INVALID: OBSERVATION_UNIVERSE_MAX_SPREAD_PCT"
        )
    if not (300 <= OBSERVATION_UNIVERSE_REFRESH_SECONDS <= 86400):
        raise ValueError(
            "CONFIG_INVALID: OBSERVATION_UNIVERSE_REFRESH_SECONDS"
        )

    if STRUCTURE_UNIVERSE_SIZE != 30:
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_SIZE"
        )
    if not (
        STRUCTURE_UNIVERSE_SIZE
        <= STRUCTURE_UNIVERSE_PREFILTER_SIZE
        <= 250
    ):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_PREFILTER_SIZE"
        )
    if not (61 <= STRUCTURE_UNIVERSE_CANDLE_LIMIT <= 500):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_CANDLE_LIMIT"
        )
    if not (
        40
        <= STRUCTURE_UNIVERSE_MIN_COMPLETED_CANDLES
        < STRUCTURE_UNIVERSE_CANDLE_LIMIT
    ):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_MIN_COMPLETED_CANDLES"
        )
    if STRUCTURE_UNIVERSE_MIN_QUOTE_VOLUME <= 0:
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_MIN_QUOTE_VOLUME"
        )
    if not (
        0
        <= STRUCTURE_UNIVERSE_MIN_CHANGE_PCT
        < STRUCTURE_UNIVERSE_MAX_CHANGE_PCT
        <= 100
    ):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_CHANGE_RANGE"
        )
    if not (1 <= STRUCTURE_UNIVERSE_MAX_WORKERS <= 16):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_MAX_WORKERS"
        )
    if not (0 <= STRUCTURE_UNIVERSE_RETENTION_BONUS <= 0.20):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_RETENTION_BONUS"
        )
    if not (0 <= STRUCTURE_UNIVERSE_MIN_SCORE <= 1):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_MIN_SCORE"
        )
    if min(
        STRUCTURE_UNIVERSE_MAX_TREND,
        STRUCTURE_UNIVERSE_MAX_BREAKOUT,
        STRUCTURE_UNIVERSE_MAX_REVERSION,
    ) < 1:
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_CATEGORY_CAP"
        )
    if (
        STRUCTURE_UNIVERSE_MAX_TREND
        + STRUCTURE_UNIVERSE_MAX_BREAKOUT
        + STRUCTURE_UNIVERSE_MAX_REVERSION
        < STRUCTURE_UNIVERSE_SIZE
    ):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_CATEGORY_CAP_TOTAL"
        )
    if STRUCTURE_UNIVERSE_ENABLED and not (
        STRUCTURE_UNIVERSE_MARKET_BASE_URL
    ):
        raise ValueError(
            "CONFIG_INVALID: STRUCTURE_UNIVERSE_MARKET_BASE_URL"
        )
    if not OBSERVATION_UNIVERSE_MARKET_BASE_URL:
        raise ValueError(
            "CONFIG_INVALID: OBSERVATION_UNIVERSE_MARKET_BASE_URL"
        )
    if not UNIVERSE_SNAPSHOT_PATH:
        raise ValueError("CONFIG_INVALID: UNIVERSE_SNAPSHOT_PATH")
    if not OBSERVATION_UNIVERSE_SNAPSHOT_PATH:
        raise ValueError(
            "CONFIG_INVALID: OBSERVATION_UNIVERSE_SNAPSHOT_PATH"
        )
    if UNIVERSE_SNAPSHOT_PATH == OBSERVATION_UNIVERSE_SNAPSHOT_PATH:
        raise ValueError(
            "CONFIG_INVALID: UNIVERSE_SNAPSHOT_PATH_CONFLICT"
        )

    candidate_score_weights = (
        CANDIDATE_SCORE_RULE_WEIGHT,
        CANDIDATE_SCORE_TREND_WEIGHT,
        CANDIDATE_SCORE_VOLATILITY_WEIGHT,
        CANDIDATE_SCORE_CANDLE_WEIGHT,
        CANDIDATE_SCORE_LOCATION_WEIGHT,
        CANDIDATE_SCORE_CONSISTENCY_WEIGHT,
    )
    if any(weight < 0 or weight > 1 for weight in candidate_score_weights):
        raise ValueError("CONFIG_INVALID: CANDIDATE_SCORE_WEIGHT_RANGE")
    if abs(sum(candidate_score_weights) - 1.0) > 1e-9:
        raise ValueError("CONFIG_INVALID: CANDIDATE_SCORE_WEIGHTS_SUM")

    if not (0 < CANDIDATE_RISK_MIN_STOP_PCT <= 10):
        raise ValueError("CONFIG_INVALID: CANDIDATE_RISK_MIN_STOP_PCT")
    if not (CANDIDATE_RISK_MIN_STOP_PCT <= CANDIDATE_RISK_MAX_STOP_PCT <= 20):
        raise ValueError("CONFIG_INVALID: CANDIDATE_RISK_MAX_STOP_PCT")
    if not (0.1 <= CANDIDATE_RISK_RANGE_MULTIPLIER <= 10):
        raise ValueError("CONFIG_INVALID: CANDIDATE_RISK_RANGE_MULTIPLIER")

    if not (5 <= PAPER_HEARTBEAT_INTERVAL_SECONDS <= 3600):
        raise ValueError("CONFIG_INVALID: PAPER_HEARTBEAT_INTERVAL_SECONDS")

    if not PAPER_PREFLIGHT_SYMBOL or not PAPER_PREFLIGHT_SYMBOL.endswith("USDT"):
        raise ValueError("CONFIG_INVALID: PAPER_PREFLIGHT_SYMBOL")

    if not (2 <= PAPER_PREFLIGHT_CANDLE_LIMIT <= 100):
        raise ValueError("CONFIG_INVALID: PAPER_PREFLIGHT_CANDLE_LIMIT")

    if not (2 <= PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS <= 60):
        raise ValueError("CONFIG_INVALID: PAPER_WS_FIRST_TICK_TIMEOUT_SECONDS")

    if not (0.5 <= PAPER_REST_POLL_INTERVAL_SECONDS <= 60):
        raise ValueError("CONFIG_INVALID: PAPER_REST_POLL_INTERVAL_SECONDS")

    if not (30 <= PAPER_WS_RETRY_INTERVAL_SECONDS <= 3600):
        raise ValueError("CONFIG_INVALID: PAPER_WS_RETRY_INTERVAL_SECONDS")

    if STRATEGY_MODE not in {"STRUCTURE", "PAPER_TEST"}:
        raise ValueError("CONFIG_INVALID: STRATEGY_MODE")

    if STRATEGY_MODE == "PAPER_TEST" and EXECUTION_MODE != "SHADOW":
        raise ValueError("CONFIG_INVALID: PAPER_TEST_REQUIRES_SHADOW")

    if not (0.01 <= PAPER_TEST_MIN_MOVE_PCT <= 5):
        raise ValueError("CONFIG_INVALID: PAPER_TEST_MIN_MOVE_PCT")

    if not (0 <= PAPER_TEST_COOLDOWN_CANDLES <= 288):
        raise ValueError("CONFIG_INVALID: PAPER_TEST_COOLDOWN_CANDLES")

    if not TESTNET_TRADING_ARM_FILE:
        raise ValueError(
            "CONFIG_INVALID: TESTNET_TRADING_ARM_FILE"
        )
    if not (1 <= TESTNET_MAX_SESSION_ENTRIES <= 100):
        raise ValueError(
            "CONFIG_INVALID: TESTNET_MAX_SESSION_ENTRIES"
        )
    if not (1 <= TESTNET_MAX_ENTRY_NOTIONAL_USD <= 100000):
        raise ValueError(
            "CONFIG_INVALID: TESTNET_MAX_ENTRY_NOTIONAL_USD"
        )

    if LIVE_ADAPTER_MODE not in {"READ_ONLY", "WRITE_ENABLED"}:
        raise ValueError("CONFIG_INVALID: LIVE_ADAPTER_MODE")

    if not LIVE_TRADING_ARM_FILE:
        raise ValueError("CONFIG_INVALID: LIVE_TRADING_ARM_FILE")

    if not LIVE_SNAPSHOT_PATH:
        raise ValueError("CONFIG_INVALID: LIVE_SNAPSHOT_PATH")

    if Path(LIVE_SNAPSHOT_PATH) == Path(LIVE_TRADING_ARM_FILE):
        raise ValueError("CONFIG_INVALID: LIVE_SNAPSHOT_PATH_CONFLICT")

    if LIVE_ORDER_WRITES_ENABLED:
        raise ValueError("CONFIG_INVALID: LIVE_ORDER_WRITES_NOT_IMPLEMENTED")

    if LIVE_ADAPTER_MODE == "WRITE_ENABLED":
        raise ValueError("CONFIG_INVALID: LIVE_WRITE_ADAPTER_NOT_IMPLEMENTED")

    if (
        TRADING_ENV == "LIVE"
        and EXECUTION_MODE == "TRADE"
        and LIVE_TRADING_CONFIRMATION
        != _REQUIRED_LIVE_TRADING_CONFIRMATION
    ):
        raise ValueError("CONFIG_INVALID: LIVE_TRADING_NOT_CONFIRMED")

    if not (0 <= MAX_SPREAD_PCT <= 5):
        raise ValueError("CONFIG_INVALID: MAX_SPREAD_PCT")


_validate()
del _validate
del _REQUIRED_LIVE_TRADING_CONFIRMATION
del _REQUIRED_TESTNET_TRADING_CONFIRMATION

