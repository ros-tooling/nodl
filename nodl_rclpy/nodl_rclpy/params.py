"""Runtime parameter listener and typed params snapshot.

Analogous to the ParamListener / Params pair produced by generate_parameter_library,
but implemented entirely at runtime without code generation.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Dict

from rcl_interfaces.msg import ParameterDescriptor, ParameterType, SetParametersResult
from rclpy.exceptions import ParameterUninitializedException
from rclpy.parameter import Parameter as RclpyParameter

from nodl.models import Parameter

if TYPE_CHECKING:
    import rclpy.node


# Maps NoDL type string to rcl_interfaces ParameterType int (used in descriptors).
_NODL_TO_PARAM_TYPE: Dict[str, int] = {
    'bool': ParameterType.PARAMETER_BOOL,
    'int': ParameterType.PARAMETER_INTEGER,
    'double': ParameterType.PARAMETER_DOUBLE,
    'string': ParameterType.PARAMETER_STRING,
    'byte_array': ParameterType.PARAMETER_BYTE_ARRAY,
    'bool_array': ParameterType.PARAMETER_BOOL_ARRAY,
    'int_array': ParameterType.PARAMETER_INTEGER_ARRAY,
    'double_array': ParameterType.PARAMETER_DOUBLE_ARRAY,
    'string_array': ParameterType.PARAMETER_STRING_ARRAY,
}

# Maps NoDL type string to rclpy Parameter.Type enum (used when declaring without a default).
_NODL_TO_RCLPY_TYPE: Dict[str, RclpyParameter.Type] = {
    'bool': RclpyParameter.Type.BOOL,
    'int': RclpyParameter.Type.INTEGER,
    'double': RclpyParameter.Type.DOUBLE,
    'string': RclpyParameter.Type.STRING,
    'byte_array': RclpyParameter.Type.BYTE_ARRAY,
    'bool_array': RclpyParameter.Type.BOOL_ARRAY,
    'int_array': RclpyParameter.Type.INTEGER_ARRAY,
    'double_array': RclpyParameter.Type.DOUBLE_ARRAY,
    'string_array': RclpyParameter.Type.STRING_ARRAY,
}


class NodlParams(SimpleNamespace):
    """Typed snapshot of declared NoDL parameters, accessible as attributes.

    Constructed by NodlParameterListener.get_params().  Attributes correspond
    to parameter names; values are Python-typed (float, int, bool, str, list).
    """


class NodlParameterListener:
    """Declares NoDL parameters on a node and maintains a live snapshot.

    Usage mirrors generate_parameter_library's ParamListener::get_params():

        self.param_listener_ = NodlParameterListener(self, doc.parameters)
        self.params_ = self.param_listener_.get_params()
    """

    def __init__(self, node: 'rclpy.node.Node', parameters: Dict[str, Parameter]):
        self._node = node
        self._snapshot: dict = {}

        for name, spec in parameters.items():
            descriptor = ParameterDescriptor(
                description=spec.description or '',
                read_only=bool(spec.read_only),
                type=_NODL_TO_PARAM_TYPE[spec.type],
            )
            if spec.default_value is not None:
                node.declare_parameter(name, spec.default_value, descriptor)
            else:
                node.declare_parameter(name, _NODL_TO_RCLPY_TYPE[spec.type], descriptor)

            try:
                self._snapshot[name] = node.get_parameter(name).value
            except ParameterUninitializedException:
                self._snapshot[name] = None

        node.add_on_set_parameters_callback(self._on_set_parameters)

    def _on_set_parameters(self, params):
        for p in params:
            if p.name in self._snapshot:
                self._snapshot[p.name] = p.value
        return SetParametersResult(successful=True)

    def get_params(self) -> NodlParams:
        """Return a snapshot of current parameter values."""
        return NodlParams(**self._snapshot)
