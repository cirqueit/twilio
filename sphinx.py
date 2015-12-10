from os import environ, path
from pocketsphinx.pocketsphinx import *
from sphinxbase.sphinxbase import *

MODEL_DIR = "pocketsphinx/model"
DATA_DIR = "pocketsphinx/test/data"

config = Decoder.default_config()
config.set_string('-hmm', path.join(MODEL_DIR, 'hmm/en-us/hub4wsj_sc_8k'))
config.set_string('-lm', path.join(MODEL_DIR, 'lm/en-us/hub4.5000.DMP'))
config.set_string('-dict', path.join(MODEL_DIR, 'lm/en-us/cmu07a.dic'))
decoder = Decoder(config)
decoder.start_utt()
stream = open(path.join(DATA_DIR, 'goforward.raw'), 'rb')
while True:
    buf = stream.read(1024)
    if buf:
        decoder.process_raw(buf, False, False)
    else:
        break
decoder.end_utt()
print ('Best hypothesis segments: ', [seg.word for seg in decoder.seg()])
