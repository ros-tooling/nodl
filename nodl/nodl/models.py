"""Typed in-memory representation of a NoDL document."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict

ParameterTypeLiteral = Literal[
    'bool', 'int', 'double', 'string',
    'bool_array', 'int_array', 'double_array', 'string_array',
]


class QoS(BaseModel):
    model_config = ConfigDict(extra='forbid')

    history: Literal['KEEP_LAST', 'KEEP_ALL', 'SYSTEM_DEFAULT']
    depth: Optional[int] = None
    reliability: Literal['RELIABLE', 'BEST_EFFORT', 'SYSTEM_DEFAULT', 'BEST_AVAILABLE']
    durability: Optional[Literal['TRANSIENT_LOCAL', 'VOLATILE', 'SYSTEM_DEFAULT', 'BEST_AVAILABLE']] = None
    deadline_ns: Optional[int] = None
    lifespan_ns: Optional[int] = None
    liveliness: Optional[Literal['AUTOMATIC', 'MANUAL_BY_TOPIC', 'SYSTEM_DEFAULT', 'BEST_AVAILABLE']] = None
    liveliness_lease_duration_ns: Optional[int] = None


class TopicEndpoint(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str
    type: str
    description: Optional[str] = None
    qos: QoS


class ServiceEndpoint(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str
    type: str
    description: Optional[str] = None


class ActionEndpoint(BaseModel):
    model_config = ConfigDict(extra='forbid')

    name: str
    type: str
    description: Optional[str] = None


class Parameter(BaseModel):
    model_config = ConfigDict(extra='forbid')

    type: ParameterTypeLiteral
    description: Optional[str] = None
    default_value: Optional[Any] = None
    read_only: Optional[bool] = None
    additional_constraints: Optional[str] = None


class FragmentRef(BaseModel):
    model_config = ConfigDict(extra='forbid')

    ref: str
    name: Optional[str] = None


class NodlDocument(BaseModel):
    model_config = ConfigDict(extra='forbid')

    nodl_version: Optional[int] = None
    description: Optional[str] = None
    base: Optional[Literal['node', 'lifecycle_node']] = None
    fragments: Optional[List[FragmentRef]] = None
    parameters: Optional[Dict[str, Parameter]] = None
    publishers: Optional[List[TopicEndpoint]] = None
    subscriptions: Optional[List[TopicEndpoint]] = None
    service_servers: Optional[List[ServiceEndpoint]] = None
    service_clients: Optional[List[ServiceEndpoint]] = None
    action_servers: Optional[List[ActionEndpoint]] = None
    action_clients: Optional[List[ActionEndpoint]] = None

    def to_dict(self) -> dict:
        """Serialize to a plain dict, omitting None fields."""
        return self.model_dump(exclude_none=True)
