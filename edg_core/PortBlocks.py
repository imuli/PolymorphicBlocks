from __future__ import annotations

from typing import *

import edgir
from .Categories import InternalBlock
from .Core import Refable
from .HierarchyBlock import Block, abstract_block
from .IdentityDict import IdentityDict
from .Ports import BasePort, Port


@abstract_block
class PortBridge(InternalBlock, Block):
  """Defines rules for connecting the internal port of a hierarchy block to a link.
  Only needed if the internal port connects to an internal link and is NOT a one-to-one forwarding port.

  Note: this is a regular block in the IR, but is conceptually different and inferred in the frontend for ease-of-use.

  Example: a power sink internal port can connect to one power sink port on an internal block without a port bridge,
  but requires a port bridge to connect to a power link that serves multiple power sinks on internal blocks.
  """
  def __init__(self):
    super().__init__()
    # TODO these should be type Port[Any], but that seems to break type inference
    self.outer_port: Any
    self.inner_link: Any

  def __setattr__(self, name: str, value):
    if isinstance(value, Port):
      assert name == '_parent' or name == "outer_port" or name == "inner_link", \
        "PortBridge can only have outer_port or inner_link ports, got %s" % name
    super().__setattr__(name, value)

  T = TypeVar('T', bound=BasePort)
  def Port(self, tpe: T, *args, **kwargs) -> T:
    assert 'optional' not in kwargs, f"Ports in PortBridge are optional by default, required should be set by enclosing block, in {kwargs}"
    return super().Port(tpe, *args, optional=True, **kwargs)

  def _get_ref_map(self, prefix: edgir.LocalPath) -> IdentityDict[Refable, edgir.LocalPath]:
    if self.__class__ == PortBridge:  # TODO: hack to allow this to elaborate as abstract class while being invalid
      return IdentityDict()

    return super()._get_ref_map(prefix)


AdapterDstType = TypeVar('AdapterDstType', bound=Port)
@abstract_block
class PortAdapter(InternalBlock, Block, Generic[AdapterDstType]):
  """Defines an adapter from one port type to another port type. This behaves as a normal block, and both the src and
   dst are connected with normal connect semantics. Should only be inferred on internal block ports."""
  def __init__(self):
    super().__init__()
    # TODO these should be type Port[Any], but that seems to break type inference
    self.src: Any
    self.dst: AdapterDstType

  def __setattr__(self, name: str, value):
    if isinstance(value, Port):
      assert name == '_parent' or name == "src" or name == "dst", \
        "PortAdapter can only have src or dst ports, got %s" % name
    super().__setattr__(name, value)

  T = TypeVar('T', bound=BasePort)
  def Port(self, tpe: T, *args, **kwargs) -> T:
    assert 'optional' not in kwargs, "Ports in PortBridge are optional by default, required should be set by enclosing block"
    return super().Port(tpe, *args, optional=True, **kwargs)

  # TODO: dedup w/ BaseBlock
  def _get_ref_map(self, prefix: edgir.LocalPath) -> IdentityDict[Refable, edgir.LocalPath]:
    if self.__class__ == PortAdapter:  # TODO: hack to allow this to elaborate as abstract class while being invalid
      return IdentityDict()

    # return super().get_ref_map(prefix) +  # TODO: dedup w/ BaseBlock, and does this break anything?
    return IdentityDict(
      *[param._get_ref_map(edgir.localpath_concat(prefix, name)) for (name, param) in self._parameters.items()],
      self.src._get_ref_map(edgir.localpath_concat(prefix, 'src')),
      self.dst._get_ref_map(edgir.localpath_concat(prefix, 'dst'))
    )
