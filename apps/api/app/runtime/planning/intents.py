from app.modules.commands.enums import CommandCategory
from app.runtime.contracts import RuntimeIntentType

COMMAND_CATEGORY_TO_RUNTIME_INTENT: dict[CommandCategory, RuntimeIntentType] = {
    CommandCategory.ON_DEMAND_READ: RuntimeIntentType.ON_DEMAND_READ,
    CommandCategory.REMOTE_DISCONNECT: RuntimeIntentType.DISCONNECT,
    CommandCategory.REMOTE_RECONNECT: RuntimeIntentType.RECONNECT,
    CommandCategory.CLOCK_SYNC: RuntimeIntentType.CLOCK_SYNC,
    CommandCategory.PROFILE_CAPTURE: RuntimeIntentType.READ_PROFILE,
    CommandCategory.CONNECTIVITY_TEST: RuntimeIntentType.CONNECTIVITY_TEST,
    CommandCategory.CONFIG_PUSH: RuntimeIntentType.CONFIG_PUSH,
}


def map_command_category_to_runtime_intent(category: CommandCategory) -> RuntimeIntentType:
    return COMMAND_CATEGORY_TO_RUNTIME_INTENT.get(category, RuntimeIntentType.GENERIC_COMMAND)
