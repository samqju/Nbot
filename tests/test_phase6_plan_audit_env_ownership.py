import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXECUTION_ENV = ROOT / "deploy" / "examples" / "execution.env.example"
OBSERVATION_ENV = ROOT / "deploy" / "examples" / "observation.env.example"


def env_values(path: Path) -> dict[str, str]:
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


class Phase6PlanAuditEnvOwnershipTests(unittest.TestCase):
    def test_removed_settings_are_absent_from_both_roles(self):
        forbidden = {
            "PAPER_HEARTBEAT_INTERVAL_SECONDS",
            "PAPER_POSITION_PRICE_MAX_AGE_SECONDS",
            "PAPER_TEST_MIN_MOVE_PCT",
            "PAPER_TEST_COOLDOWN_CANDLES",
        }
        self.assertTrue(forbidden.isdisjoint(env_values(EXECUTION_ENV)))
        self.assertTrue(forbidden.isdisjoint(env_values(OBSERVATION_ENV)))

    def test_both_roles_can_select_live_or_testnet_public_market(self):
        required = {
            "TRADING_ENV",
            "EXECUTION_MODE",
            "LIVE_BASE_URL",
            "LIVE_MARKET_WS_URL",
            "TESTNET_BASE_URL",
            "TESTNET_MARKET_WS_URL",
            "OBSERVATION_CONTROL_TOKEN",
        }
        self.assertTrue(required.issubset(env_values(EXECUTION_ENV)))
        self.assertTrue(required.issubset(env_values(OBSERVATION_ENV)))

    def test_execution_owns_private_credentials_and_trade_gates(self):
        execution = env_values(EXECUTION_ENV)
        required = {
            "TESTNET_API_KEY",
            "TESTNET_API_SECRET",
            "TESTNET_USER_WS_URL",
            "TESTNET_TRADING_CONFIRMATION",
            "TESTNET_TRADING_ARM_FILE",
            "TESTNET_MAX_SESSION_ENTRIES",
            "TESTNET_MAX_ENTRY_NOTIONAL_USD",
            "LIVE_API_KEY",
            "LIVE_API_SECRET",
            "LIVE_USER_WS_URL",
            "LIVE_TRADING_CONFIRMATION",
            "LIVE_ADAPTER_MODE",
            "LIVE_ORDER_WRITES_ENABLED",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
            "TELEGRAM_OPERATOR_USER_ID",
            "TESTNET_EXECUTION_OUTBOX_PATH",
            "LIVE_EXECUTION_OUTBOX_PATH",
        }
        self.assertTrue(required.issubset(execution))
        self.assertEqual(execution["TESTNET_MAX_SESSION_ENTRIES"], "5")
        self.assertEqual(execution["TESTNET_TRADING_CONFIRMATION"], "DISABLED")
        self.assertEqual(execution["LIVE_TRADING_CONFIRMATION"], "DISABLED")
        self.assertEqual(execution["LIVE_ADAPTER_MODE"], "READ_ONLY")
        self.assertEqual(execution["LIVE_ORDER_WRITES_ENABLED"], "false")

    def test_observation_has_no_private_or_capital_authority(self):
        observation = env_values(OBSERVATION_ENV)
        forbidden = {
            "TESTNET_API_KEY",
            "TESTNET_API_SECRET",
            "TESTNET_USER_WS_URL",
            "TESTNET_TRADING_CONFIRMATION",
            "TESTNET_TRADING_ARM_FILE",
            "LIVE_API_KEY",
            "LIVE_API_SECRET",
            "LIVE_USER_WS_URL",
            "LIVE_TRADING_CONFIRMATION",
            "LIVE_ADAPTER_MODE",
            "LIVE_ORDER_WRITES_ENABLED",
            "LIVE_TRADING_ARM_FILE",
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
            "TELEGRAM_OPERATOR_USER_ID",
            "TESTNET_BOT_STATE_PATH",
            "LIVE_BOT_STATE_PATH",
            "TESTNET_EXECUTION_OUTBOX_PATH",
            "LIVE_EXECUTION_OUTBOX_PATH",
        }
        self.assertTrue(forbidden.isdisjoint(observation))

    def test_observation_explicitly_keeps_learning_enabled(self):
        observation = env_values(OBSERVATION_ENV)
        self.assertEqual(observation["STRATEGY_MODE"], "STRUCTURE")
        for key in (
            "SHADOW_MODEL_SCORING_ENABLED",
            "SHADOW_DECISION_TESTING_ENABLED",
            "VIRTUAL_LAB_ENABLED",
            "AUTO_TRAINING_ENABLED",
            "AUTOMATIC_PROMOTION_ENABLED",
            "PAPER_CANARY_EXECUTION_ENABLED",
            "PAPER_CANARY_CONTROLLER_ENABLED",
        ):
            self.assertEqual(observation[key], "true")
        self.assertEqual(observation["OBSERVATION_UNIVERSE_SIZE"], "200")
        self.assertEqual(observation["STRUCTURE_UNIVERSE_SIZE"], "30")

    def test_shared_paper_cost_assumptions_match(self):
        execution = env_values(EXECUTION_ENV)
        observation = env_values(OBSERVATION_ENV)
        for key in (
            "PAPER_TAKER_FEE_RATE",
            "PAPER_ENTRY_SLIPPAGE_PCT",
            "PAPER_EXIT_SLIPPAGE_PCT",
        ):
            self.assertEqual(execution[key], observation[key])


if __name__ == "__main__":
    unittest.main()
