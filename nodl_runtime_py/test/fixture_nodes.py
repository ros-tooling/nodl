# SPDX-FileCopyrightText: 2026 Open Source Robotics Foundation, Inc.
# SPDX-License-Identifier: Apache-2.0
"""Node classes for the nodl_runtime_py tests, each printing what the tests wait for."""

import threading
import time

import rclpy
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.node import Node

READY = 'ready'
SHUTDOWN = 'on_shutdown called'
CONTEXT_SHUTDOWN = 'context shutdown'


class ReadyNode(Node):
    """Print READY and the executor type from its first timer callback."""

    def __init__(self):
        super().__init__('ready_node')
        self._timer = self.create_timer(0.01, self._on_timer)

    def _on_timer(self):
        self._timer.cancel()
        print(f'{READY} {type(self.executor).__name__}', flush=True)


class ActivatedNode(LifecycleNode):
    """Print READY once activated."""

    def __init__(self):
        super().__init__('activated_node')

    def on_activate(self, state):
        print(READY, flush=True)
        return super().on_activate(state)


class FailingConfigureNode(LifecycleNode):
    def __init__(self):
        super().__init__('failing_configure_node')

    def on_configure(self, state):
        return TransitionCallbackReturn.FAILURE


class FailingActivateNode(LifecycleNode):
    def __init__(self):
        super().__init__('failing_activate_node')

    def on_activate(self, state):
        return TransitionCallbackReturn.FAILURE


class SelfShutdownNode(Node):
    """Shut rclpy down from its first timer callback."""

    def __init__(self):
        super().__init__('self_shutdown_node')
        self.create_timer(0.01, rclpy.shutdown)


class RaisingNode(Node):
    def __init__(self):
        raise RuntimeError('fixture constructor failure')


class ThreadShutdownNode(Node):
    """Shut rclpy down from a thread of its own."""

    def __init__(self):
        super().__init__('thread_shutdown_node')
        threading.Timer(0.1, rclpy.shutdown).start()


class BlockingCallbackNode(Node):
    """Print READY, then block in its first timer callback."""

    def __init__(self):
        super().__init__('blocking_callback_node')
        self._timer = self.create_timer(0.01, self._on_timer)

    def _on_timer(self):
        self._timer.cancel()
        print(READY, flush=True)
        time.sleep(60)


class BlockingConstructorNode(Node):
    """Print READY, then block in the constructor."""

    def __init__(self):
        print(READY, flush=True)
        time.sleep(60)
        super().__init__('blocking_constructor_node')


class ShutdownHookNode(LifecycleNode):
    """Print READY once activated, and print when shut down."""

    def __init__(self):
        super().__init__('shutdown_hook_node')

    def on_activate(self, state):
        print(READY, flush=True)
        return super().on_activate(state)

    def on_shutdown(self, state):
        print(SHUTDOWN, flush=True)
        return super().on_shutdown(state)


class ThreadShutdownLifecycleNode(ShutdownHookNode):
    """Shut rclpy down from a thread of its own, once activated."""

    def on_activate(self, state):
        threading.Timer(0.1, rclpy.shutdown).start()
        return super().on_activate(state)


class DestroyRaisesNode(Node):
    """Print READY, and fail to be destroyed the first time.

    The second attempt succeeds, because Lyrical's rclpy.shutdown destroys the nodes still registered with the context,
    and a node that failed to be destroyed is still registered.
    """

    def __init__(self):
        super().__init__('destroy_raises_node')
        self._destroy_failed = False
        self.context.on_shutdown(lambda: print(CONTEXT_SHUTDOWN, flush=True))
        self._timer = self.create_timer(0.01, self._on_timer)

    def _on_timer(self):
        self._timer.cancel()
        print(READY, flush=True)

    def destroy_node(self):
        if not self._destroy_failed:
            self._destroy_failed = True
            raise RuntimeError('fixture cleanup failure')
        super().destroy_node()


class CallbackAndDestroyRaiseNode(DestroyRaisesNode):
    """Fail in the first timer callback as well."""

    def _on_timer(self):
        raise RuntimeError('fixture callback failure')


class ParameterNode(Node):
    """Print READY and the value of the greeting parameter."""

    def __init__(self):
        super().__init__('parameter_node')
        greeting = self.declare_parameter('greeting', 'unset').value
        self._timer = self.create_timer(0.01, lambda: self._on_timer(greeting))

    def _on_timer(self, greeting):
        self._timer.cancel()
        print(f'{READY} {greeting}', flush=True)
