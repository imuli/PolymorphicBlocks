from typing import *
import re
from electronics_abstract_parts import *

from .JlcPart import JlcTablePart, DescriptionParser


class JlcBaseFet(BaseTableFet, JlcTablePart):
  PACKAGE_FOOTPRINT_MAP = {
    'SOT23-3': 'Package_TO_SOT_SMD:SOT-23',
    'SOT-23-3': 'Package_TO_SOT_SMD:SOT-23',
    'SOT-23-3L': 'Package_TO_SOT_SMD:SOT-23',
    'TO-252': 'Package_TO_SOT_SMD:TO-252-2',  # aka DPak
    'TO-252-2': 'Package_TO_SOT_SMD:TO-252-2',
    'TO-263-2': 'Package_TO_SOT_SMD:TO-263-2',  # aka D2Pak
    'SOT-223': 'Package_TO_SOT_SMD:SOT-223-3_TabPin2',
    'SOT-223-3': 'Package_TO_SOT_SMD:SOT-223-3_TabPin2',
    'SO-8': 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
    'SOIC-8_3.9x4.9x1.27P': 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
    'SOP-8': 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
    'SOP-8_3.9x4.9x1.27P': 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
  }

  DESCRIPTION_PARSERS: List[DescriptionParser] = [
    (re.compile("(\S+V) (\S+A) (\S+W) (\S+Ω)@(\S+V),\S+A (\S+V)@\S+A ([PN]) Channel .* MOSFETs.*"),
     lambda match: {
       JlcBaseFet.CHANNEL: match.group(7),
       TableFet.VDS_RATING: Range.zero_to_upper(PartParserUtil.parse_value(match.group(1), 'V')),
       TableFet.IDS_RATING: Range.zero_to_upper(PartParserUtil.parse_value(match.group(2), 'A')),
       # Vgs isn't specified, so the Ron@Vgs is used as a lower bound; assumed symmetric
       TableFet.VGS_RATING: Range.from_abs_tolerance(0,
                                                     PartParserUtil.parse_value(match.group(5), 'V')),
       TableFet.VGS_DRIVE: Range(PartParserUtil.parse_value(match.group(6), 'V'),
                                 PartParserUtil.parse_value(match.group(5), 'V')),
       TableFet.RDS_ON: Range.zero_to_upper(PartParserUtil.parse_value(match.group(4), 'Ω')),
       TableFet.POWER_RATING: Range.zero_to_upper(PartParserUtil.parse_value(match.group(3), 'W')),
       TableFet.GATE_CHARGE: Range.zero_to_upper(3000e-9),  # not specified, pessimistic upper bound
     }),
    # Some of them have the power entry later, for whatever reason
    (re.compile("(\S+V) (\S+A) (\S+Ω)@(\S+V),\S+A (\S+W) (\S+V)@\S+A ([PN]) Channel .* MOSFETs.*"),
     lambda match: {
       JlcBaseFet.CHANNEL: match.group(7),
       TableFet.VDS_RATING: Range.zero_to_upper(PartParserUtil.parse_value(match.group(1), 'V')),
       TableFet.IDS_RATING: Range.zero_to_upper(PartParserUtil.parse_value(match.group(2), 'A')),
       # Vgs isn't specified, so the Ron@Vgs is used as a lower bound; assumed symmetric
       TableFet.VGS_RATING: Range.from_abs_tolerance(0,
                                                     PartParserUtil.parse_value(match.group(4), 'V')),
       TableFet.VGS_DRIVE: Range(PartParserUtil.parse_value(match.group(6), 'V'),
                                 PartParserUtil.parse_value(match.group(4), 'V')),
       TableFet.RDS_ON: Range.zero_to_upper(PartParserUtil.parse_value(match.group(3), 'Ω')),
       TableFet.POWER_RATING: Range.zero_to_upper(PartParserUtil.parse_value(match.group(5), 'W')),
       TableFet.GATE_CHARGE: Range.zero_to_upper(3000e-9),  # not specified, pessimistic upper bound
     }),
  ]

  @classmethod
  def _make_table(cls) -> PartsTable:
    def parse_row(row: PartsTableRow) -> Optional[Dict[PartsTableColumn, Any]]:
      if row['Second Category'] != 'MOSFETs':
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


class JlcFet(JlcBaseFet, TableFet):
  def _make_footprint(self, part: PartsTableRow) -> None:
    super()._make_footprint(part)
    self.assign(self.lcsc_part, part[self.LCSC_PART_HEADER])
    self.assign(self.actual_basic_part, part[self.BASIC_PART_HEADER] == self.BASIC_PART_VALUE)


class JlcSwitchFet(JlcBaseFet, TableSwitchFet):
  def _make_footprint(self, part: PartsTableRow) -> None:
    super()._make_footprint(part)
    self.assign(self.lcsc_part, part[self.LCSC_PART_HEADER])
    self.assign(self.actual_basic_part, part[self.BASIC_PART_HEADER] == self.BASIC_PART_VALUE)
