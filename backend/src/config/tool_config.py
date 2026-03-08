from pydantic import BaseModel, ConfigDict, Field


class ToolGroupConfig(BaseModel):
    """Config section for a tool group"""

    name: str = Field(..., description="Unique name for the tool group")
    model_config = ConfigDict(extra="allow")


class ToolConfig(BaseModel):
    """Config section for a tool"""

    name: str = Field(..., description="Unique name for the tool")
    group: str = Field(..., description="Group name for the tool")
    use: str = Field(
        ...,
        description="Variable name of the tool provider(e.g. src.sandbox.tools:bash_tool)",
    )
    key_env_var: str | None = Field(
        default=None,
        description="Environment variable name for this tool's API key (e.g. TAVILY_API_KEY). "
        "When set, the user's stored secret for this key takes priority over the platform default.",
    )
    model_config = ConfigDict(extra="allow")
