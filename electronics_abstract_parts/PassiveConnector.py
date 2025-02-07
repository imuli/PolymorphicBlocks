from typing import List, Tuple, Iterable
from electronics_abstract_parts import *


@abstract_block
class PassiveConnector(InternalSubcircuit, GeneratorBlock, FootprintBlock):
  """A base Block that is an elastic n-ported connector with passive type.
  Intended as an infrastructural block where a particular connector series is not fixed,
  but can be selected through the refinements system.
  An optional length argument can be specified, which forces total number of pins. This must be larger
  than the maximum pin index (but can be smaller, unassigned pins are NC).
  The allocated pin names correlate with the footprint pin, 1-indexed (per electronics convention).
  It is up to the instantiating layer to set the pinmap (or allow the user to set it by refinements)."""
  allowed_pins: Iterable[int]

  @init_in_parent
  def __init__(self, length: IntLike = 0):
    super().__init__()
    self.pins = self.Port(Vector(Passive().empty()))
    self.actual_length = self.Parameter(IntExpr())

    self.generator(self.generate, length, self.pins.requested())

  def part_footprint_mfr_name(self, length: int) -> Tuple[str, str, str]:
    """Returns the part footprint, manufacturer, and name given the number of pins (length).
    Implementing classes must implement this method."""
    raise NotImplementedError

  def generate(self, length: int, pins: List[str]):
    max_pin_index = 0
    for pin in pins:
      self.pins.append_elt(Passive(), pin)
      assert pin != '0', "cannot have zero pin, explicit pin numbers through suggested_name are required"
      max_pin_index = max(max_pin_index, int(pin))
    if length == 0:
      length = max_pin_index

    self.assign(self.actual_length, length)
    self.require(max_pin_index <= self.actual_length,
                 f"maximum pin index {max_pin_index} over requested length {length}")
    # TODO ideally this is require, but we don't support set ops in the IR
    assert length in self.allowed_pins, f"requested length {length} outside allowed length {self.allowed_pins}"

    (footprint, mfr, part) = self.part_footprint_mfr_name(length)
    self.footprint(
      'J', footprint,
      {pin: self.pins[pin] for pin in pins},
      mfr, part
    )
