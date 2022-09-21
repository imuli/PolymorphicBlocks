from electronics_abstract_parts import *
from electronics_lib import Fpc050


class Er_Oled_091_3_Device(DiscreteChip):
    """15-pin FPC connector for the ER-OLED-0.91-3* device, configured to run off
    internal DC/DC
    https://www.buydisplay.com/download/manual/ER-OLED0.91-3_Series_Datasheet.pdf"""
    def __init__(self) -> None:
        super().__init__()

        self.conn = self.Block(Fpc050(length=15))

        self.vcc = self.Export(self.conn.pins.allocate('15').adapt_to(VoltageSource(
            voltage_out=(6.4, 9),
            current_limits=0*mAmp(tol=0)  # external draw not allowed, probably does 10-16mA
        )))
        self.vdd = self.Export(self.conn.pins.allocate('7').adapt_to(VoltageSink(
            voltage_limits=(1.65, 4)*Volt,  # use the absolute maximum upper limit to allow tolerance on 3.3v
            current_draw=(1, 300)*uAmp
        )))
        # this provides a way to modify the minimum Vbat, which apparently works lower than the datasheet specification
        # and is needed to drive both Vbat and Vdd off of a common 3.3v supply
        # default of 3.3 is using SSD1306 datasheet v1.6, the panel datasheet is more restrictive
        self.vbat_min = self.Parameter(FloatExpr(3.3*Volt))
        self.vbat = self.Export(self.conn.pins.allocate('5').adapt_to(VoltageSink(
            voltage_limits=(self.vbat_min, 4.2*Volt),
            current_draw=(23, 29)*mAmp
        )))
        self.vss = self.Export(self.conn.pins.allocate('6').adapt_to(Ground()), [Common])

        din_model = DigitalSink.from_supply(
            self.vss, self.vdd,
            voltage_limit_tolerance=(-0.3, 0.3),  # SSD1306 datasheet, Table 11-1
            input_threshold_factor=(0.2, 0.8)
        )

        self.spi = self.Port(SpiSlave.empty())
        self.connect(self.spi.sck, self.conn.pins.allocate('11').adapt_to(din_model))
        self.connect(self.spi.mosi, self.conn.pins.allocate('12').adapt_to(din_model))
        self.spi.miso.not_connected()

        self.dc = self.Export(self.conn.pins.allocate('10').adapt_to(din_model))
        self.res = self.Export(self.conn.pins.allocate('9').adapt_to(din_model))
        self.cs = self.Export(self.conn.pins.allocate('8').adapt_to(din_model))

        self.vcomh = self.Export(self.conn.pins.allocate('14'))
        self.iref = self.Export(self.conn.pins.allocate('13'))
        self.c2p = self.Export(self.conn.pins.allocate('1'))
        self.c2n = self.Export(self.conn.pins.allocate('2'))
        self.c1p = self.Export(self.conn.pins.allocate('3'))
        self.c1n = self.Export(self.conn.pins.allocate('4'))


class Er_Oled_091_3(Lcd, Block):
    """SSD1306-based 0.91" 128x32 monochrome OLED.
    TODO (maybe?) add the power gating circuit in the reference schematic"""
    def __init__(self) -> None:
        super().__init__()
        self.device = self.Block(Er_Oled_091_3_Device())
        self.gnd = self.Export(self.device.vss, [Common])
        self.pwr = self.Export(self.device.vdd, [Power])
        self.reset = self.Export(self.device.res)
        self.spi = self.Export(self.device.spi)
        self.cs = self.Export(self.device.cs)
        self.dc = self.Export(self.device.dc)

    def contents(self):
        super().contents()

        self.connect(self.pwr, self.device.vbat)

        self.c1_cap = self.Block(Capacitor(0.1*uFarad(tol=0.2), (0, 6.3)*Volt))
        self.connect(self.c1_cap.pos, self.device.c1p)
        self.connect(self.c1_cap.neg, self.device.c1n)
        self.c2_cap = self.Block(Capacitor(0.1*uFarad(tol=0.2), (0, 6.3)*Volt))
        self.connect(self.c2_cap.pos, self.device.c2p)
        self.connect(self.c2_cap.neg, self.device.c2n)
        self.vcomh_cap = self.Block(Capacitor(2.2*uFarad(tol=0.2), (0, 16)*Volt))
        self.connect(self.vcomh_cap.pos, self.device.vcomh)
        self.connect(self.vcomh_cap.neg.adapt_to(Ground()), self.gnd)
        self.iref_res = self.Block(Resistor(resistance=560*kOhm(tol=0.05)))  # TODO dynamic sizing
        self.connect(self.iref_res.a, self.device.iref)
        self.connect(self.iref_res.b.adapt_to(Ground()), self.gnd)

        self.vdd_cap1 = self.Block(DecouplingCapacitor(capacitance=0.1*uFarad(tol=0.2))).connected(self.gnd, self.pwr)
        self.vdd_cap2 = self.Block(DecouplingCapacitor(capacitance=4.7*uFarad(tol=0.2))).connected(self.gnd, self.pwr)

        self.vcc_cap1 = self.Block(DecouplingCapacitor(capacitance=0.1*uFarad(tol=0.2)))\
            .connected(self.gnd, self.device.vcc)
        self.vcc_cap2 = self.Block(DecouplingCapacitor(capacitance=4.7*uFarad(tol=0.2)))\
            .connected(self.gnd, self.device.vcc)