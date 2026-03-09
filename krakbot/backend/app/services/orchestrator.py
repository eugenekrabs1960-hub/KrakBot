class OrchestratorService:
    """Bot + strategy runtime state machine (skeleton)."""

    def __init__(self):
        self.bot_state = "stopped"

    def apply_command(self, command: str) -> str:
        allowed = {"start", "stop", "pause", "resume", "reload"}
        if command not in allowed:
            raise ValueError(f"unsupported command: {command}")
        self.bot_state = command
        return self.bot_state
