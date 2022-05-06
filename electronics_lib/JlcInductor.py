from typing import *
import re
from electronics_abstract_parts import *

from .JlcPart import JlcTablePart, DescriptionParser


class JlcInductor(TableInductor, JlcTablePart, FootprintBlock):
  PACKAGE_FOOTPRINT_MAP = {
    'L0603': 'Inductor_SMD:L_0603_1608Metric',
    '0603': 'Inductor_SMD:L_0603_1608Metric',
    'L0805': 'Inductor_SMD:L_0805_2012Metric',
    '0805': 'Inductor_SMD:L_0805_2012Metric',
    'L1206': 'Inductor_SMD:L_1206_3216Metric',
    '1206': 'Inductor_SMD:L_1206_3216Metric',
    '1210': 'Inductor_SMD:L_1210_3225Metric',
    'L1210': 'Inductor_SMD:L_1210_3225Metric',
    '1812': 'Inductor_SMD:L_1812_4532Metric',
    'L1812': 'Inductor_SMD:L_1812_4532Metric',
  }

  DESCRIPTION_PARSERS: List[DescriptionParser] = [
    (re.compile("(\S+A) (\S+H) (±\S+%) (\S+Ω) .* Inductors.*"),
     lambda match: {
       TableInductor.INDUCTANCE: Range.from_tolerance(PartsTableUtil.parse_value(match.group(2), 'H'),
                                                      PartsTableUtil.parse_tolerance(match.group(3))),
       TableInductor.FREQUENCY_RATING: Range(0, 0),  # user must waive frequency check
       TableInductor.CURRENT_RATING: Range.zero_to_upper(PartsTableUtil.parse_value(match.group(1), 'A')),
       TableInductor.DC_RESISTANCE: Range.zero_to_upper(PartsTableUtil.parse_value(match.group(4), 'Ω')),
     }),
    (re.compile("(\S+A) (\S+H) ±(\S+H) (\S+Ω) .* Inductors.*"),
     lambda match: {
       TableInductor.INDUCTANCE: Range.from_abs_tolerance(PartsTableUtil.parse_value(match.group(2), 'H'),
                                                          PartsTableUtil.parse_value(match.group(3), 'H')),
       TableInductor.FREQUENCY_RATING: Range(0, 0),  # user must waive frequency check
       TableInductor.CURRENT_RATING: Range.zero_to_upper(PartsTableUtil.parse_value(match.group(1), 'A')),
       TableInductor.DC_RESISTANCE: Range.zero_to_upper(PartsTableUtil.parse_value(match.group(4), 'Ω')),
     }),
  ]

  @classmethod
  def _make_table(cls) -> PartsTable:
    def parse_row(row: PartsTableRow) -> Optional[Dict[PartsTableColumn, Any]]:
      if row['Second Category'] != 'Inductors (SMD)':
        return None
      footprint = cls.PACKAGE_FOOTPRINT_MAP.get(row[cls._PACKAGE_HEADER])
      if footprint is None:
        return None

      new_cols = cls.parse_full_description(row[cls.DESCRIPTION_COL], cls.DESCRIPTION_PARSERS)
      if new_cols is None:
        return None

      new_cols[cls.KICAD_FOOTPRINT] = footprint
      new_cols.update(cls._parse_jlcpcb_common(row))
      return new_cols

    return cls._jlc_table().map_new_columns(parse_row).sort_by(
      lambda row: [row[cls.BASIC_PART_HEADER], row[cls.KICAD_FOOTPRINT], row[cls.COST]]
    )

  def _make_footprint(self, part: PartsTableRow) -> None:
    super()._make_footprint(part)
    self.assign(self.lcsc_part, part[self.LCSC_PART_HEADER])
    self.assign(self.actual_basic_part, part[self.BASIC_PART_HEADER] == self.BASIC_PART_VALUE)