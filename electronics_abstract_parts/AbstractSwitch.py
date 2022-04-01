from electronics_model import *
from .Categories import *


@abstract_block
class Switch(DiscreteComponent):
  @init_in_parent
  def __init__(self, voltage: RangeLike, current: RangeLike = Default(0*Amp(tol=0))) -> None:
    super().__init__()

    self.a = self.Port(Passive.empty())
    self.b = self.Port(Passive.empty())

    self.current = self.ArgParameter(current)
    self.voltage = self.ArgParameter(voltage)


class DigitalSwitch(DiscreteApplication):
  def __init__(self) -> None:
    super().__init__()

    self.gnd = self.Port(Ground.empty(), [Common])
    self.out = self.Port(DigitalSingleSource.empty(), [Output])

  def contents(self):
    super().contents()
    self.package = self.Block(Switch(current=self.out.link().current_limits,
                                     voltage=self.out.link().voltage))

    self.connect(self.out, self.package.a.as_digital_single_source(
      voltage_out=self.gnd.link().voltage,
      output_thresholds=(self.gnd.link().voltage.upper(), float('inf')),
      pulldown_capable=False, low_signal_driver=True
    ))
    self.connect(self.gnd, self.package.b.as_ground())
