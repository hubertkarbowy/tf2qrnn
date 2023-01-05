import argparse
import os
import shutil

import tensorflow as tf

from fastai.basics import *
from fastai.callback.all import *
from fastai.text.all import *
from .fastai_lm_utils import save_as_keras
from .encoders import ExportableGenericRecurrentLM, ExportableULMFiT, ExportableULMFiTRagged, STLRSchedule
from .commons import get_rnn_layers_config


def main(args):
    os.makedirs(args['out_path'], exist_ok=True)
    state_dict = torch.load(open(args['pretrained_model'], 'rb'), map_location='cpu')
    state_dict = state_dict['model']
    exp_name = os.path.splitext(os.path.basename(args['pretrained_model']))[0]
    layer_config = get_rnn_layers_config({
        'qrnn': args.get('qrnn'),
        'num_recurrent_layers': args.get('num_recurrent_layers'),
        'enforce_rnn_api_for_lstm': True
    })

    lm_num, encoder_num, outmask_num, spm_encoder_model = save_as_keras(state_dict=state_dict,
                                                                        exp_name=exp_name,
                                                                        save_path=os.path.join(args['out_path'], 'keras_weights'),
                                                                        spm_model_file=args['spm_model_file'],
                                                                        fixed_seq_len=args.get('fixed_seq_len'),
                                                                        layer_config=layer_config)
    print("Exported weights successfully")
    tf.keras.backend.set_learning_phase(0)
    if args.get('fixed_seq_len') is None:
        exportable = ExportableULMFiTRagged(encoder_num, outmask_num, spm_encoder_model, state_dict['1.decoder.bias'], STLRSchedule)
        convenience_signatures = {'numericalized_encoder': exportable.numericalized_encoder,
                                  'string_encoder': exportable.string_encoder,
                                  'spm_processor': exportable.string_numericalizer}
        tf.saved_model.save(exportable, os.path.join(args['out_path'], 'saved_model'), signatures=convenience_signatures)
    else:
        if layer_config['qrnn']:
            exportable = ExportableGenericRecurrentLM(encoder_num, outmask_num, spm_encoder_model, state_dict['1.decoder.bias'])
        else:
            exportable = ExportableULMFiT(encoder_num, outmask_num, spm_encoder_model, state_dict['1.decoder.bias'])
        convenience_signatures={'numericalized_encoder': exportable.numericalized_encoder,
                                'string_encoder': exportable.string_encoder,
                                'spm_processor': exportable.string_numericalizer}
        tf.saved_model.save(exportable, os.path.join(args['out_path'], 'saved_model'), signatures=convenience_signatures)
    print(f"Exported SavedModel successfully (qrnn={layer_config['qrnn']}).")
    os.makedirs(os.path.join(args['out_path'], 'fastai_model'), exist_ok=True)
    shutil.copy2(args['pretrained_model'], os.path.join(args['out_path'], 'fastai_model/'))
    print("FastAI model copied.")
    os.makedirs(os.path.join(args['out_path'], 'spm_model'), exist_ok=True)
    shutil.copy2(args['spm_model_file'], os.path.join(args['out_path'], 'spm_model/'))
    shutil.copy2(args['spm_model_file'].replace(".model", ".vocab"), os.path.join(args['out_path'], 'spm_model/'))
    print("SPM model copied. Conversion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a .pth file trained using FastAI into a Tensorflow model.\n"
                                                 "This script will produce four subdirectories containing: "
                                                 "1) Keras weights, 2) SavedModel, 3) Sentencepiece vocabulary, "
                                                 "4) FastAI model (copy)")
    parser.add_argument("--pretrained-model", required=True, help="Path to a pretrained FastAI model (.pth)")
    parser.add_argument("--qrnn", required=False, action='store_true', help="The .pth file contains a QRNN model")
    parser.add_argument("--num-recurrent-layers", required=False, type=int, help="Number of recurrent layers")
    parser.add_argument("--out-path", required=True, help="Output directory where the converted models will be saved")
    parser.add_argument("--fixed-seq-len", type=int, required=False, help="Fixed sequence length. If unset, the encoder "
                                                                          "in SavedModel will output ragged tensors.")
    parser.add_argument("--spm-model-file", required=True, help="Path to SPM model file")
    argz_ = vars(parser.parse_args())
    main(argz_)
