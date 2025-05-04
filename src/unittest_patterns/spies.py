from abc import ABCMeta
from asyncio import Future
from textwrap import dedent
from types import FunctionType, TracebackType
from typing import Awaitable, Callable, ParamSpec, TypeAlias, TypeVar

from unittest.mock import MagicMock, Mock

T = TypeVar("T")
M = ParamSpec("M")
S = ParamSpec("S")
ValueTypes: TypeAlias = int | str | bytes | float | bool
PairTypes: TypeAlias = tuple[str, ValueTypes]
CollectionTypes: TypeAlias = tuple[PairTypes] | list[PairTypes] | set[PairTypes] | dict[str, ValueTypes]


def is_subset_of(superset: CollectionTypes, subset: CollectionTypes) -> bool:
    """Check if subset is a subset of superset."""
    return dict(subset).items() <= dict(superset).items()


# TODO: Make more robust, handle more target types, and be more user friendly during development.
# - Access to the parameters class var of the dataclass LLMServiceClient does not seem to work
#   correctly.  I think this is because init=False is used, so the attribute is not seen as a class var
#   by the wrapper.
# - It would be nice if accessing the docstring of a method on the wrapper would return the docstring
#   of the target method.
# - !!!: This didn't work like I expected.  I thought that if the target instance had a method that called
#   another of its methods, that the wrapper would relflect that.  It doesn't.  The wrapper only detects the
#   methods that are called directly on it.  Fixing this is more than I can do now.
#   - Could I replace the target instance's `self` with the wrapper?
#   - Could I dynamically create a class that subclasses the target with a MagicMixin and then instantiate that?
#   - Could I replace the target instance's __getattr__ with a function that returns the wrapper?
#   - Could I use a metaclass to do this?
#   - Could I use a decorator to do this?
#   - Could I enumerate the methods of the target instance and wire everything together to get the effect I want?
#
# C901: Function is too complex
# The inclusion of the _SpyClass definition is one aspect contributing to the complexity score, but it
# cannot be factored out because the make_spy function is a closure over it.  Factoring it out would
# require making its definition more complex and overall, less elegent.
def make_spy(  # noqa: C901
    target: type[T],
    *target_args: S.args,
    wrapper: type[Mock] = MagicMock,
    **target_kwargs: S.kwargs,
) -> Callable[..., T]:
    """Wrap the target and record interactions.

    The target is expected to be a class-like object.  The wrapper is expected to be a class that is a
    subclass of Mock.  Any calls to the wrapper are passed on to an instance of the target class and allowed
    to execute normally - unless the wrapper is configured to do otherwise.

    Args:
        target: The target class to instantiate and spy on.
        wrapper: The class to use as a wrapper for the target.
        *target_args: Positional arguments passed to the target to create the instance that will be wrapped.
        **target_kwargs: Keyword arguments passed to the target to create the instance that will be wrapped.

    Returns:
        A factory function that creates a wrapped target instance.

    Raises:
        TypeError: If the target is not a class-like object.

    Examples:

        Example 1: The simplest use case is to wrap a class that takes no arguments
        and provide no additional configuration on the wrapper.  This creates
        a basic spy, a proxy, that passes

        >>> from conversationservice import llm
        >>> llm_client_spy_factory = make_spy(llm.LLMServiceClient)
        >>> llm_client_spy = llm_client_spy_factory()
        >>> payload = llm_client_spy.build_payload()
        >>> llm_client_spy.build_payload.assert_called_once_with()
        >>> is_subset_of(payload["parameters"], llm.DEFAULT_PARAMETERS)
        True
        >>> repr(llm_client_spy)
        "<MagicMock spec='LLMServiceClient()' id='4387696320'>"
        >>> isinstance(llm_client_spy, llm.LLMServiceClient)
        True

        Example 2: The factory function can be called with additional arguments to
        configure the wrapper.  The target instance accepts parameters when
        creating the factory.

        >>> from conversationservice.llm import LLMServiceClient
        >>> llm_client_spy_factory = make_spy(
        ...     LLMServiceClient,
        ...     api_url="http://llm_service.com:8000/api/v3/conversations",
        ... )
        >>> llm_client_spy = llm_client_spy_factory(name="CustomName", **{"chat.return_value": AsyncMock()})
        >>> _ = await llm_client_spy.chat("The configuration set this return value.")
        >>> llm_client_spy.chat.assert_called_once_with("The configuration set this return value.")
    """
    if type(target) not in (type, ABCMeta):
        if type(target) is FunctionType:
            raise TypeError("The target must be a class like object - received a FunctionType.")

        class_name = getattr(target, "__class__", object).__name__
        raise TypeError(f"Received an instance of {class_name}(), expected target={class_name}.")

    instance = target(*target_args, **target_kwargs)

    class _SpyFactory:
        @property
        def instance(self) -> T:
            """Return the instance of the target class."""
            return self._instance

        def __init__(self, instance: T) -> None:
            self._instance = instance

        def __call__(self, *args: M.args, **kwargs: M.kwargs) -> T:
            override = {"spec": target, "spec_set": target, "wraps": instance}
            kw = {"name": f"{target.__name__}()", **kwargs, **override}
            spy = wrapper(*args, **kw)
            spy.__doc__ = instance.__doc__

            return spy

    _factory = _SpyFactory(instance)
    _factory.__name__ = f"{target.__name__}SpyFactory"
    _factory.__doc__ = dedent(f"""Wrap the instance of {target.__name__} with a proxy that records interactions.

    The wrapped instance that was created along with this factory function is used in every call to the
    factory.  The parameters passed to the factory are applied to the wrapper.  The factory can be called repeatedly
    to create different configurations of the spy, but the instance will always be the same.  The instance itself is
    accessible through the `instance` property of the factory.

    The parameters passed to the factory are applied to the wrapper, in this case, {wrapper.__name__}, as it is
    instantiated.  The wrapper is expected to be a class that is a subclass of Mock.  The valid parameters for the
    factory correspond to the parameters of the wrapper with the exception of `spec`, `spec_set`, and `wraps` which
    will be overridden by the factory if provided.

    Args:
        *args: Positional arguments passed to the wrapper.
        **kwargs: Keyword arguments passed to the wrapper.

    Returns:
        A wrapped instance of the target class.
    """)

    return _factory


class AsyncContextManagerMock(MagicMock):
    async def __aenter__(self) -> Awaitable["AsyncContextManagerMock"]:
        """Return self when entering the context."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Awaitable[None]:
        """Do nothing when exiting the context."""
        result: Future[None] = Future()
        result.set_result(None)
        return result

