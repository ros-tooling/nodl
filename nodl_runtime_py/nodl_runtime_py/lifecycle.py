# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""A lifecycle node with sealed transition callbacks and optional ``handle_*`` hooks."""

from typing import Any, final

from lifecycle_msgs.msg import State
from rclpy.lifecycle import LifecycleNode as RclpyLifecycleNode
from rclpy.lifecycle import LifecycleState, TransitionCallbackReturn

# The transition callbacks that a subclass must not define, because this class implements them.
_SEALED_CALLBACKS = (
    'on_configure',
    'on_activate',
    'on_deactivate',
    'on_cleanup',
    'on_shutdown',
    'on_error',
)


class LifecycleNode(RclpyLifecycleNode):
    """A lifecycle node with sealed ``on_*`` transition callbacks and ``handle_*`` hooks.

    Derive it and override the ``handle_*`` hooks that need custom behavior.
    Each hook takes the previous ``LifecycleState`` and returns a ``TransitionCallbackReturn``.
    The ``on_*`` transition callbacks run the standard lifecycle management of ``rclpy``, for example activating lifecycle publishers, and call the hooks.
    A subclass that defines an ``on_*`` callback raises ``TypeError`` naming the hook to define instead when the class is defined.

    See the ``nodl_runtime_py`` overview for the order on each transition.
    """

    # True when ``handle_deactivate`` ran for the current active period.
    _nodl_deactivate_hook_ran = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        sealed = [name for name in _SEALED_CALLBACKS if name in cls.__dict__]
        if sealed:
            hooks = ', '.join(f'handle_{name.removeprefix("on_")}' for name in sealed)
            raise TypeError(
                f'{cls.__qualname__} defines {", ".join(sealed)}, which LifecycleNode implements and does not allow overriding.'
                f' Define {hooks} instead.'
            )

    @final
    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Move from unconfigured to inactive. Calls ``handle_configure``."""
        return self.handle_configure(state)

    @final
    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Move from inactive to active. Runs the standard activation, then calls ``handle_activate``.

        When ``handle_activate`` does not return SUCCESS or raises, the standard deactivation runs.
        A result other than SUCCESS is returned, and an exception propagates.
        """
        self._nodl_deactivate_hook_ran = False
        base_result = super().on_activate(state)
        if TransitionCallbackReturn.SUCCESS != base_result:
            return base_result
        try:
            hook_result = self.handle_activate(state)
        except BaseException:
            super().on_deactivate(state)
            raise
        if TransitionCallbackReturn.SUCCESS != hook_result:
            super().on_deactivate(state)
        return hook_result

    @final
    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Move from active to inactive. Calls ``handle_deactivate``, then runs the standard deactivation if it succeeded."""
        self._nodl_deactivate_hook_ran = True
        hook_result = self.handle_deactivate(state)
        if TransitionCallbackReturn.SUCCESS != hook_result:
            self._nodl_deactivate_hook_ran = False
            return hook_result
        return super().on_deactivate(state)

    @final
    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Move from inactive to unconfigured. Calls ``handle_cleanup``."""
        return self.handle_cleanup(state)

    @final
    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """End the active state, then call ``handle_shutdown``.

        From the active state this runs ``handle_deactivate`` and the standard deactivation first.
        A shutdown cannot be vetoed, so the result of ``handle_deactivate`` is ignored and an exception from it is logged.
        """
        self._end_active_state(state)
        return self.handle_shutdown(state)

    @final
    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        """End the active state, then call ``handle_error``.

        From the active state this runs ``handle_deactivate`` first, unless an exception from it caused the error,
        then the standard deactivation.
        The result of ``handle_deactivate`` is ignored and an exception from it is logged.
        """
        self._end_active_state(state)
        return self.handle_error(state)

    def handle_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the configure transition."""
        return TransitionCallbackReturn.SUCCESS

    def handle_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the activate transition, after the standard activation.

        FAILURE leaves the node inactive, and ERROR runs ``handle_error``.
        """
        return TransitionCallbackReturn.SUCCESS

    def handle_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the deactivate transition, before the standard deactivation.

        FAILURE leaves the node active, and ERROR runs ``handle_error``.
        It also runs before shutdown and error from the active state, where the result is ignored.
        """
        return TransitionCallbackReturn.SUCCESS

    def handle_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the cleanup transition."""
        return TransitionCallbackReturn.SUCCESS

    def handle_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the shutdown transition, after the standard deactivation."""
        return TransitionCallbackReturn.SUCCESS

    def handle_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        """Called on the error transition, after the standard deactivation.

        SUCCESS takes the node to the unconfigured state, and any other result finalizes it.
        """
        return TransitionCallbackReturn.SUCCESS

    def _end_active_state(self, state: LifecycleState) -> None:
        """Run the deactivation that shutdown and error need: the authored hook if the node is active, then the standard one."""
        if State.PRIMARY_STATE_ACTIVE == state.state_id and not self._nodl_deactivate_hook_ran:
            self._nodl_deactivate_hook_ran = True
            try:
                if TransitionCallbackReturn.SUCCESS != self.handle_deactivate(state):
                    self.get_logger().warning('handle_deactivate did not succeed, and the shutdown continues')
            except Exception as error:
                self.get_logger().error(f'handle_deactivate raised, and the shutdown continues: {error!r}')
        super().on_deactivate(state)
