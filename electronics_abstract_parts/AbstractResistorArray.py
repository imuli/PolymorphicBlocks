from typing import List

from electronics_model import *
from .AbstractResistor import Resistor
from .PartsTable import PartsTableColumn, PartsTableRow
from .PartsTablePart import PartsTableFootprint
from .Categories import *
from .StandardPinningFootprint import StandardPinningFootprint


class ResistorArrayElement(Resistor):  # to avoid an abstract part error
  def __init__(self):
    super().__init__(resistance=RangeExpr(), power=RangeExpr())


@abstract_block
class ResistorArray(PassiveComponent, MultipackBlock):
  """An n-element resistor array, where all resistors have the same resistance and power rating."""
  @init_in_parent
  def __init__(self, count: IntLike = 0) -> None:  # 0 means 'size automatically'
    super().__init__()

    self.count = self.ArgParameter(count)

    self.elements = self.PackedPart(PackedBlockArray(ResistorArrayElement()))
    self.a = self.PackedExport(self.elements.ports_array(lambda x: x.a))
    self.b = self.PackedExport(self.elements.ports_array(lambda x: x.b))
    self.resistances = self.PackedParameter(self.elements.params_array(lambda x: x.resistance))
    self.powers = self.PackedParameter(self.elements.params_array(lambda x: x.power))

    self.actual_count = self.Parameter(IntExpr())
    self.actual_resistance = self.Parameter(RangeExpr())
    self.actual_power_rating = self.Parameter(RangeExpr())  # per element

    self.unpacked_assign(self.elements.params(lambda x: x.actual_resistance), self.actual_resistance)
    self.unpacked_assign(self.elements.params(lambda x: x.actual_power_rating), self.actual_power_rating)

  def contents(self):
    super().contents()

    self.description = DescriptionString(  # TODO better support for array typed
      "<b>count:</b> ", DescriptionString.FormatUnits(self.actual_count, ""),  # TODO unitless
      " <b>of spec</b> ", DescriptionString.FormatUnits(self.count, ""), "\n",
      "<b>resistance:</b> ", DescriptionString.FormatUnits(self.actual_resistance, "Ω"),
      " <b>of specs</b> ", DescriptionString.FormatUnits(self.resistances, "Ω"), "\n",
      "<b>element power:</b> ", DescriptionString.FormatUnits(self.actual_power_rating, "W"),
      " <b>of operating:</b> ", DescriptionString.FormatUnits(self.powers, "W")
    )


@non_library
class ResistorArrayStandardPinning(ResistorArray, StandardPinningFootprint[ResistorArray]):
  # TODO some way to ensure the resistor count is sufficient?
  FOOTPRINT_PINNING_MAP = {  # these are all the footprints in KiCad as of 2022 05 31
    (
      'Resistor_SMD:R_Array_Concave_2x0603',
      'Resistor_SMD:R_Array_Convex_2x0402',
      'Resistor_SMD:R_Array_Convex_2x0603',
      'Resistor_SMD:R_Array_Convex_2x0606',
      'Resistor_SMD:R_Array_Convex_2x1206',
    ): lambda block: {
      '1': block.a['0'],
      '4': block.b['0'],
      '2': block.a['1'],
      '3': block.b['1'],
    },
    (
      'Resistor_SMD:R_Array_Concave_4x0402',
      'Resistor_SMD:R_Array_Concave_4x0603',
      'Resistor_SMD:R_Array_Convex_4x0402',
      'Resistor_SMD:R_Array_Convex_4x0603',
      'Resistor_SMD:R_Array_Convex_4x0612',
      'Resistor_SMD:R_Array_Convex_4x1206',
    ): lambda block: {
      '1': block.a['0'],
      '8': block.b['0'],
      '2': block.a['1'],
      '7': block.b['1'],
      '3': block.a['2'],
      '6': block.b['2'],
      '4': block.a['3'],
      '5': block.b['3'],
    },
  }


@non_library
class TableResistorArray(ResistorArrayStandardPinning, PartsTableFootprint, GeneratorBlock):
  RESISTANCE = PartsTableColumn(Range)
  POWER_RATING = PartsTableColumn(Range)
  COUNT = PartsTableColumn(int)

  @init_in_parent
  def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    self.generator(self.select_part, self.count, self.a.requested(), self.b.requested(),
                   self.resistances, self.powers, self.part, self.footprint_spec)

  def select_part(self, count: int, a_requests: List[str], b_requests: List[str],
                  resistances: List[Range], power_dissipations: List[Range],
                  part_spec: str, footprint_spec: str) -> None:
    # TODO some kind of range intersect construct?
    resistances_min = max([resistance.lower for resistance in resistances])
    resistances_max = min([resistance.upper for resistance in resistances])
    assert resistances_min <= resistances_max, "resistances do not intersect"
    resistance_intersect = Range(resistances_min, resistances_max)

    powers_min = min([power.lower for power in power_dissipations])
    powers_max = max([power.upper for power in power_dissipations])
    powers_hull = Range(powers_min, powers_max)

    parts = self._get_table().filter(lambda row: (
            (not part_spec or part_spec == row[self.PART_NUMBER_COL]) and
            (not footprint_spec or footprint_spec == row[self.KICAD_FOOTPRINT]) and
            (count == 0 or count == row[self.COUNT]) and
            (row[self.COUNT] >= len(a_requests) and row[self.COUNT] >= len(b_requests)) and
            row[self.RESISTANCE].fuzzy_in(resistance_intersect) and
            powers_hull.fuzzy_in(row[self.POWER_RATING])
    ))
    part = parts.first(f"no resistors in {resistance_intersect} Ohm, {powers_hull} W")

    # actually create terminals
    for i in range(part[self.COUNT]):
      self.a.append_elt(Passive(), str(i))
      self.b.append_elt(Passive(), str(i))

    self.assign(self.actual_count, part[self.COUNT])
    self.assign(self.actual_part, part[self.PART_NUMBER_COL])
    self.assign(self.matching_parts, parts.map(lambda row: row[self.PART_NUMBER_COL]))
    self.assign(self.actual_resistance, part[self.RESISTANCE])
    self.assign(self.actual_power_rating, part[self.POWER_RATING])

    self._make_footprint(part)

  def _make_footprint(self, part: PartsTableRow) -> None:
    self.footprint(
      'RN', part[self.KICAD_FOOTPRINT],
      self._make_pinning(part[self.KICAD_FOOTPRINT]),
      mfr=part[self.MANUFACTURER_COL], part=part[self.PART_NUMBER_COL],
      value=part[self.DESCRIPTION_COL],
      datasheet=part[self.DATASHEET_COL]
    )
