from gnuradio import gr
from gnuradio import eng_notation
from gnuradio.eng_option import eng_option
from optparse import OptionParser

# From gr-digital
from gnuradio import digital

# from current dir
from transmit_path import transmit_path
from uhd_interface import uhd_transmitter
from receive_path import receive_path
from uhd_interface import uhd_receiver

import struct
import time

#top block

class my_top_block(gr.top_block):
    def __init__(self, modulator, demodulator, rx_callback, options):
        gr.top_block.__init__(self)

        args = modulator.extract_kwargs_from_options(options)
        symbol_rate = options.bitrate / modulator(**args).bits_per_symbol()
        self.txsink = uhd_transmitter(options.args, symbol_rate,
                                    options.samples_per_symbol,
                                    options.tx_freq, options.tx_gain,
                                    options.spec, options.tx_antenna,
                                    options.verbose)
        options.samples_per_symbol = self.txsink._sps

        self.rxsource = uhd_receiver(options.args, symbol_rate,
                                   options.samples_per_symbol,
                                   options.rx_freq, options.rx_gain,
                                   options.spec, options.rx_antenna,
                                   options.verbose)
        options.samples_per_symbol = self.rxsource._sps
    
        self.txpath = transmit_path(modulator, options)        
        self.connect(self.txpath, self.txsink)

        self.rxpath = receive_path(demodulator, rx_callback, options) 
        self.connect(self.rxsource, self.rxpath)

#//////////////////////////////////////////////////////////////////////////
#			main            
#/////////////////////////////////////////////////////////////////////////

# Stop and wait ARQ : Tx sends a packet. It starts a timer when a packet is sent. If an ack requesting
# next packet is received before the timeout it sends the next packet. On timeout it sends the current
# packet agian.

global request_no
def main():

    global request_no
    request_no = 0
    sink_file = open("sinc_audio", 'w')


    def send_pkt(payload='', eof=False):
        (no,) = (struct.unpack('!H', payload[0:2]))
        return tb.txpath.send_pkt(payload, eof)

    def rx_callback(ok, payload):
        global request_no
        (sequence_no,) = struct.unpack('!H', payload[0:2])
        if ok:
            if sequence_no == request_no:
                request_no = request_no + 1
                sink_file.write(payload[2:])
            data = (pkt_size - 2) * chr(request_no & 0xff)
            payload = struct.pack('!H', request_no & 0xffff) + data
            send_pkt(payload)

        print "Ok = %5s packet = %4d " % (
                ok, sequence_no)

    mods = digital.modulation_utils.type_1_mods()
    demods = digital.modulation_utils.type_1_demods()

    # Create Options Parser:
    parser = OptionParser (option_class=eng_option, conflict_handler="resolve")
    expert_grp = parser.add_option_group("Expert")

    parser.add_option("-s", "--size", type="eng_float", default=1500,
                      help="set packet size [default=%default]")
    parser.add_option("-m", "--modulation", type="choice", choices=mods.keys(), 
                      default='psk',
                      help="Select modulation from: %s [default=%%default]"
                            % (', '.join(mods.keys()),))

    transmit_path.add_options(parser, expert_grp)
    uhd_transmitter.add_options(parser)
    receive_path.add_options(parser, expert_grp)
    uhd_receiver.add_options(parser)
    
    for mod in mods.values():
        mod.add_options(expert_grp)
    for mod in demods.values():
        mod.add_options(expert_grp)

    (options, args) = parser.parse_args ()
    pkt_size = int(options.size)

    tb = my_top_block(mods[options.modulation], demods[options.modulation], rx_callback, options)

    tb.start()
    tb.wait()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
