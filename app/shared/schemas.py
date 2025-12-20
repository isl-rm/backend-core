from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    """Convert snake_case field names to lowerCamelCase for API payloads."""
    if "_" not in value:
        return value
    head, *tail = value.split("_")
    return head + "".join(word.capitalize() for word in tail if word)


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)
