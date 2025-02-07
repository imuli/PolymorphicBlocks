from __future__ import annotations

from typing import *
from edg_core import *
from edg_core.Blocks import DescriptionString
from .CircuitBlock import CircuitPortBridge, CircuitLink, CircuitPortAdapter
from .Units import Volt, Amp, Ohm

if TYPE_CHECKING:
  from .DigitalPorts import DigitalSource
  from .AnalogPort import AnalogSource


class VoltageLink(CircuitLink):
  def __init__(self) -> None:
    super().__init__()

    self.source = self.Port(VoltageSource())
    self.sinks = self.Port(Vector(VoltageSink()))

    self.voltage = self.Parameter(RangeExpr())
    self.voltage_limits = self.Parameter(RangeExpr())
    self.current_drawn = self.Parameter(RangeExpr())
    self.current_limits = self.Parameter(RangeExpr())

  def contents(self) -> None:
    super().contents()

    self.description = DescriptionString(
      "<b>voltage</b>: ", DescriptionString.FormatUnits(self.voltage, "V"),
      " <b>of limits</b>: ", DescriptionString.FormatUnits(self.voltage_limits, "V"),
      "\n<b>current</b>: ", DescriptionString.FormatUnits(self.current_drawn, "A"),
      " <b>of limits</b>: ", DescriptionString.FormatUnits(self.current_limits, "A"))

    self.assign(self.voltage, self.source.voltage_out)
    self.assign(self.voltage_limits, self.sinks.intersection(lambda x: x.voltage_limits))
    self.require(self.voltage_limits.contains(self.voltage), "overvoltage")
    self.assign(self.current_limits, self.source.current_limits)

    self.assign(self.current_drawn, self.sinks.sum(lambda x: x.current_draw))
    self.require(self.current_limits.contains(self.current_drawn), "overcurrent")


class VoltageSinkBridge(CircuitPortBridge):
  def __init__(self) -> None:
    super().__init__()

    self.outer_port = self.Port(VoltageSink(current_draw=RangeExpr(),
                                            voltage_limits=RangeExpr()))

    # Here we ignore the current_limits of the inner port, instead relying on the main link to handle it
    # The outer port's voltage_limits is untouched and should be defined in the port def.
    # TODO: it's a slightly optimization to handle them here. Should it be done?
    # TODO: or maybe current_limits / voltage_limits shouldn't be a port, but rather a block property?
    self.inner_link = self.Port(VoltageSource(current_limits=RangeExpr.ALL,
                                              voltage_out=RangeExpr()))

  def contents(self) -> None:
    super().contents()

    self.assign(self.outer_port.current_draw, self.inner_link.link().current_drawn)
    self.assign(self.outer_port.voltage_limits, self.inner_link.link().voltage_limits)

    self.assign(self.inner_link.voltage_out, self.outer_port.link().voltage)


class VoltageSourceBridge(CircuitPortBridge):  # basic passthrough port, sources look the same inside and outside
  def __init__(self) -> None:
    super().__init__()

    self.outer_port = self.Port(VoltageSource(voltage_out=RangeExpr(),
                                              current_limits=RangeExpr()))

    # Here we ignore the voltage_limits of the inner port, instead relying on the main link to handle it
    # The outer port's current_limits is untouched and should be defined in tte port def.
    # TODO: it's a slightly optimization to handle them here. Should it be done?
    # TODO: or maybe current_limits / voltage_limits shouldn't be a port, but rather a block property?
    self.inner_link = self.Port(VoltageSink(voltage_limits=RangeExpr.ALL,
                                            current_draw=RangeExpr()))

  def contents(self) -> None:
    super().contents()

    self.assign(self.outer_port.voltage_out, self.inner_link.link().voltage)
    self.assign(self.outer_port.current_limits, self.inner_link.link().current_limits)  # TODO adjust for inner current drawn

    self.assign(self.inner_link.current_draw, self.outer_port.link().current_drawn)


CircuitLinkType = TypeVar('CircuitLinkType', bound=Link)
class CircuitPort(Port[CircuitLinkType], Generic[CircuitLinkType]):
  """Electrical connection that represents a single port into a single copper net"""
  pass


class VoltageBase(CircuitPort[VoltageLink]):
  link_type = VoltageLink

  # TODO: support isolation domains and offset grounds

  # these are here (instead of in VoltageSource) since the port may be on the other side of a bridge
  def as_digital_source(self) -> DigitalSource:
    return self._convert(VoltageSinkAdapterDigitalSource())

  def as_analog_source(self) -> AnalogSource:
    return self._convert(VoltageSinkAdapterAnalogSource())


class VoltageSink(VoltageBase):
  bridge_type = VoltageSinkBridge

  @staticmethod
  def from_gnd(gnd: VoltageSink, voltage_limits: RangeLike = Default(RangeExpr.ALL),
               current_draw: RangeLike = Default(RangeExpr.ZERO)) -> 'VoltageSink':
    return VoltageSink(
      voltage_limits=voltage_limits - gnd.link().voltage,
      current_draw = current_draw
    )

  def __init__(self, voltage_limits: RangeLike = Default(RangeExpr.ALL),
               current_draw: RangeLike = Default(RangeExpr.ZERO)) -> None:
    super().__init__()
    self.voltage_limits: RangeExpr = self.Parameter(RangeExpr(voltage_limits))
    self.current_draw: RangeExpr = self.Parameter(RangeExpr(current_draw))


class VoltageSinkAdapterDigitalSource(CircuitPortAdapter['DigitalSource']):
  @init_in_parent
  def __init__(self):
    from .DigitalPorts import DigitalSource
    super().__init__()
    self.src = self.Port(VoltageSink(
      voltage_limits=RangeExpr.ALL * Volt,
      current_draw=RangeExpr()
    ))
    self.dst = self.Port(DigitalSource(
      voltage_out=self.src.link().voltage,
      # TODO propagation of current limits?
      output_thresholds=(0, self.src.link().voltage.lower())
    ))
    self.assign(self.src.current_draw, self.dst.link().current_drawn)  # TODO might be an overestimate


class VoltageSinkAdapterAnalogSource(CircuitPortAdapter['AnalogSource']):
  @init_in_parent
  def __init__(self):
    from .AnalogPort import AnalogSource

    super().__init__()
    self.src = self.Port(VoltageSink(
      voltage_limits=(-float('inf'), float('inf'))*Volt,
      current_draw=RangeExpr()
    ))
    self.dst = self.Port(AnalogSource(
      voltage_out=self.src.link().voltage,
      impedance=(0, 0)*Ohm,  # TODO not actually true, but pretty darn low?
    ))

    # TODO might be an overestimate
    # TODO debug the type ignore. Seems to go away after poking, and reappears on a dmypy restart
    # Perhaps a circular reference issue?
    self.assign(self.src.current_draw, self.dst.link().current_drawn)  # type: ignore


class VoltageSource(VoltageBase):
  bridge_type = VoltageSourceBridge

  def __init__(self, voltage_out: RangeLike = Default(RangeExpr.ZERO),
               current_limits: RangeLike = Default(RangeExpr.ALL)) -> None:
    super().__init__()
    self.voltage_out: RangeExpr = self.Parameter(RangeExpr(voltage_out))
    self.current_limits: RangeExpr = self.Parameter(RangeExpr(current_limits))


Power = PortTag(VoltageSink)  # General positive voltage port, should only be mutually exclusive with the below
