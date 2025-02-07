from electronics_abstract_parts import *


class CustomFet(FetStandardPinning, GeneratorBlock):
  @init_in_parent
  def __init__(self, *args, footprint_spec: StringLike = Default(""),
               manufacturer_spec: StringLike = Default(""), part_spec: StringLike = Default(""), **kwargs):
    super().__init__(*args, **kwargs)
    self.footprint_spec = self.ArgParameter(footprint_spec)  # actual_footprint left to the actual footprint
    self.manufacturer_spec = self.ArgParameter(manufacturer_spec)
    self.part_spec = self.ArgParameter(part_spec)
    self.generator(self.generate, self.footprint_spec)

    # use ideal specs, which can be overridden with refinements
    self.assign(self.actual_drain_voltage_rating, Range.all())
    self.assign(self.actual_drain_current_rating, Range.all())
    self.assign(self.actual_gate_voltage_rating, Range.all())
    self.assign(self.actual_gate_drive, Range.zero_to_upper(0))
    self.assign(self.actual_power_rating, Range.all())
    self.assign(self.actual_rds_on, Range.zero_to_upper(0))
    self.assign(self.actual_gate_charge, Range.zero_to_upper(0))

  def generate(self, footprint_spec: str) -> None:
    self.footprint(
      'Q', footprint_spec,
      self._make_pinning(footprint_spec),
      mfr=self.manufacturer_spec, part=self.part_spec,
      value=self.part_spec,
      datasheet=""
    )
