import functools

from electronics_abstract_parts import *
from .JlcPart import JlcPart


class Drv8313_Device(InternalSubcircuit, FootprintBlock, JlcPart):
    def __init__(self) -> None:
        super().__init__()
        self.vm = self.Port(VoltageSink(  # one 0.1uF capacitor per supply pin and a bulk Vm capacitor
            voltage_limits=(8, 60)*Volt,  # Table 6.3 Vm
            current_draw=RangeExpr(),
        ))
        self.v3p3 = self.Port(VoltageSource(  # internal regulator, bypass with 6.3v, 0.47uF capacitor
            voltage_out=(3.1, 3.52)*Volt,  # Table 6.5 V3P3 voltage
            current_limits=(0, 10)*mAmp,  # Table 6.3 max V3P3 load current
        ))
        self.vcp = self.Port(Passive())  # charge pump, 16V 0.1uF capacitor to Vm
        self.gnd = self.Port(Ground())

        self.ens = self.Port(Vector(DigitalSink.empty()))
        self.ins = self.Port(Vector(DigitalSink.empty()))
        self.outs = self.Port(Vector(DigitalSource.empty()))

        self.din_model = DigitalSink(  # nSleep, ENx, INx - internally pulled down 100k (Table 6.5)
            voltage_limits=(-0.3, 5.25)*Volt,  # to input high voltage max
            input_thresholds=(0.7, 2.2)
        )
        self.nreset = self.Port(self.din_model)  # required to be driven, to clear fault conditions
        self.nsleep = self.Port(self.din_model)  # required, though can be tied high
        self.nfault = self.Port(DigitalSingleSource.low_from_supply(self.gnd), optional=True)

        self.pgnds = self.Port(Vector(VoltageSink.empty()))

        self.cpl = self.Port(Passive())  # connect Vm rated, 0.01uF ceramic capacitor
        self.cph = self.Port(Passive())

    def contents(self) -> None:
        out_model = DigitalSource.from_supply(
            self.gnd, self.vm,
            current_limits=(-2.5, 2.5)*Amp  # peak current, section 1
        )
        pgnd_model = VoltageSink(
            voltage_limits=(-0.5, 0.5)*Volt,  # Table 6.3 PGNDx voltage
            current_draw=-self.vm.current_draw,
        )
        channel_currents = []
        out_connected = []
        for i in ['1', '2', '3']:
            en_i = self.ens.append_elt(self.din_model, i)
            in_i = self.ins.append_elt(self.din_model, i)
            out_i = self.outs.append_elt(out_model, i)
            self.pgnds.append_elt(pgnd_model, i)

            self.require(out_i.is_connected().implies(en_i.is_connected() & in_i.is_connected()))
            channel_currents.append(
                out_i.is_connected().then_else(out_i.link().current_drawn.abs().upper(), 0*mAmp)
            )
            out_connected.append(out_i.is_connected())

        overall_current = functools.reduce(lambda a, b: a.max(b), channel_currents)
        self.assign(self.vm.current_draw, (0.5, 5)*mAmp +  # Table 6.5 Vm sleep typ to operating max
                    (0,  overall_current))
        any_out_connected = functools.reduce(lambda a, b: a | b, out_connected)
        self.require(any_out_connected)

        self.footprint(
            'U', 'Package_SO:HTSSOP-28-1EP_4.4x9.7mm_P0.65mm_EP2.85x5.4mm_ThermalVias',
            {
                '1': self.cpl,
                '2': self.cph,
                '3': self.vcp,
                '4': self.vm,
                '5': self.outs['1'],
                '6': self.pgnds['1'],
                '7': self.pgnds['2'],
                '8': self.outs['2'],
                '9': self.outs['3'],
                '10': self.pgnds['3'],
                '11': self.vm,
                '12': self.gnd,  # compp  # uncommitted comparator input
                '13': self.gnd,  # compn  # uncommitted comparator input
                '14': self.gnd,
                '15': self.v3p3,
                '16': self.nreset,
                '17': self.nsleep,
                '18': self.nfault,  # open-drain fault status (requires external pullup)
                # '19': self.ncompo,  # uncommitted comparator output
                '20': self.gnd,
                # '21': self.nc,
                '22': self.ens['3'],
                '23': self.ins['3'],
                '24': self.ens['2'],
                '25': self.ins['2'],
                '26': self.ens['1'],
                '27': self.ins['1'],
                '28': self.gnd,

                '29': self.gnd,  # exposed pad
            },
            mfr='Texas Instruments', part='DRV8313PWP',
            datasheet='https://www.ti.com/lit/ds/symlink/drv8313.pdf'
        )
        self.assign(self.lcsc_part, 'C92482')


class Drv8313(BldcDriver, Block):
    def __init__(self) -> None:
        super().__init__()
        self.ic = self.Block(Drv8313_Device())
        self.pwr = self.Export(self.ic.vm)
        self.gnd = self.Export(self.ic.gnd, [Common])

        self.ens = self.Export(self.ic.ens)
        self.ins = self.Export(self.ic.ins)
        self.nreset = self.Export(self.ic.nreset)  # required to be driven, to clear fault conditions
        self.nsleep = self.Port(DigitalSink.empty(), optional=True)  # tied high if not connected
        self.nfault = self.Export(self.ic.nfault, optional=True)

        self.outs = self.Export(self.ic.outs)
        self.pgnds = self.Port(Vector(VoltageSink.empty()), optional=True)  # connected in the generator if used

    def contents(self):
        super().contents()
        self.vm_cap_bulk = self.Block(DecouplingCapacitor((10*0.8, 100)*uFarad)).connected(self.gnd, self.ic.vm)
        self.vm_cap1 = self.Block(DecouplingCapacitor((0.1*0.8, 100)*uFarad)).connected(self.gnd, self.ic.vm)
        self.vm_cap2 = self.Block(DecouplingCapacitor((0.1*0.8, 100)*uFarad)).connected(self.gnd, self.ic.vm)

        # TODO datasheet recommends 6.3v-rated cap, here we just derive it from the voltage rail
        self.v3p3_cap = self.Block(DecouplingCapacitor(0.47*uFarad(tol=0.2))).connected(self.gnd, self.ic.v3p3)

        vm_voltage = self.pwr.link().voltage - self.gnd.link().voltage
        self.cp_cap = self.Block(Capacitor(0.01*uFarad(tol=0.2), vm_voltage))
        self.connect(self.cp_cap.pos, self.ic.cph)
        self.connect(self.cp_cap.neg, self.ic.cpl)

        self.vcp_cap = self.Block(Capacitor(0.1*uFarad(tol=0.2), (0, 16)*Volt))
        self.connect(self.vcp_cap.pos, self.ic.vcp)
        self.connect(self.vcp_cap.neg.adapt_to(VoltageSink()), self.ic.vm)

        self.nsleep_default = self.Block(DigitalSourceConnected()) \
            .out_with_default(self.ic.nsleep, self.nsleep, self.ic.v3p3.as_digital_source())

        self.pgnd_defaults = ElementDict[VoltageSourceConnected]()
        for i in ['1', '2', '3']:
            pgnd = self.pgnds.append_elt(VoltageSink.empty(), i)
            self.pgnd_defaults[i] = self.Block(VoltageSourceConnected())\
                .out_with_default(self.ic.pgnds.request(i), pgnd, self.gnd)
