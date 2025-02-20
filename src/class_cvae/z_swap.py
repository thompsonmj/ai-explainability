import os
import random
from argparse import ArgumentParser

import numpy as np

import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from torchvision.datasets import MNIST
from torchvision.transforms import ToTensor

from PIL import Image, ImageDraw, ImageFont
import matplotlib.pyplot as plt

from models import Encoder, Decoder, Classifier, ImageClassifier


"""
Goal: Create visual counterfactual
"""


def load_data():
    test_dset = MNIST(root="data", train=False, transform=ToTensor())

    return test_dset

def create_img_from_text(width, height, text):
    PAD = 2
    img_size = img.shape[:2]
    text_img = (np.ones((height, width, 3)) * 255).astype(np.uint8)
    text_img = Image.fromarray(text_img)
    text_img_dr = ImageDraw.Draw(text_img)
    font = ImageFont.load_default()
    text_img_dr.text((PAD, PAD), text, font=font, fill=(0, 0, 0))
    text_img = np.array(text_img)[:, :, :1]

    return text_img

def save_imgs(reals, fakes, confs, org_confs, output):
    reals = reals.cpu().detach().numpy()
    fakes = fakes.cpu().detach().numpy()

    reals = np.transpose(reals, (0, 2, 3, 1)) * 255
    fakes = np.transpose(fakes, (0, 2, 3, 1)) * 255
    diffs = (reals - fakes)
    diffs_pos = np.copy(diffs)
    diffs_pos[diffs_pos < 0] = 0
    diffs_neg = np.copy(diffs)
    diffs_neg[diffs_neg > 0] = 0
    diffs_neg *= -1

    final = None
    for i in range(len(reals)):
        if final is None:
            final = create_img_from_text(reals.shape[1], 14, f"{int(round(org_confs[i].item(), 2)*100)}%")
        else:
            final = np.concatenate((final, create_img_from_text(reals.shape[1], 14, f"{int(round(org_confs[i].item(), 2)*100)}%")), axis=1)
    
    tmp = None
    for i in range(len(reals)):
        if tmp is None:
            tmp = create_img_from_text(reals.shape[1], 14, f"{int(round(confs[i].item(), 2)*100)}%")
        else:
            tmp = np.concatenate((tmp, create_img_from_text(reals.shape[1], 14, f"{int(round(confs[i].item(), 2)*100)}%")), axis=1)
    final = np.concatenate((final, tmp), axis=0)[:, :, :1].astype(np.uint8)
    
    tmp = None
    for img in reals:
        if tmp is None:
            tmp = img
        else:
            tmp = np.concatenate((tmp, img), axis=1)
    final = np.concatenate((final, tmp), axis=0)[:, :, :1].astype(np.uint8)

    tmp = None
    for img in fakes:
        if tmp is None:
            tmp = img
        else:
            tmp = np.concatenate((tmp, img), axis=1)

    final = np.concatenate((final, tmp), axis=0)[:, :, :1].astype(np.uint8)
    
    tmp = None
    for img in diffs_pos:
        if tmp is None:
            tmp = img
        else:
            tmp = np.concatenate((tmp, img), axis=1)

    final = np.concatenate((final, tmp), axis=0)[:, :, :1].astype(np.uint8)
    
    tmp = None
    for img in diffs_neg:
        if tmp is None:
            tmp = img
        else:
            tmp = np.concatenate((tmp, img), axis=1)

    final = np.concatenate((final, tmp), axis=0)[:, :, :1].astype(np.uint8)

    Image.fromarray(final[:, :, 0]).save(output)

def get_args():
    parser = ArgumentParser()
    parser.add_argument('--src_lbl', type=int, default=7)
    parser.add_argument('--tgt_lbl', type=int, default=1)
    parser.add_argument('--batch_size', type=int, default=1)
    parser.add_argument('--encoder', type=str, default=None)
    parser.add_argument('--decoder', type=str, default=None)
    parser.add_argument('--classifier', type=str, default=None)
    parser.add_argument('--img_classifier', type=str, default=None)
    parser.add_argument('--reinput', action="store_true", default=False)
    parser.add_argument('--output', type=str, default="swap.png")
    parser.add_argument('--num_features', type=int, default=20)

    return parser.parse_args()


def set_seed(seed=2023):
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)

def calc_img_diff_loss(org_img_recon, imgs_recon, loss_fn):
    diffs = (org_img_recon - imgs_recon)
    loss = min_loss_fn(diffs, torch.zeros_like(diffs).cuda())
    return loss

def save_z_chg(z_chg, output="z.png"):
    # output is broken
    z = z_chg.detach().cpu().numpy()
    plt.bar(np.arange(len(z)), z)
    plt.savefig(output)
    plt.close()


if __name__ == "__main__":
    set_seed()
    args = get_args()
    test_dset = load_data()

    src_img = None
    tgt_img = None
    for img, lbl in test_dset:
        if lbl == args.src_lbl:
            src_img = img.cuda().unsqueeze(0)
        elif lbl == args.tgt_lbl:
            tgt_img = img.cuda().unsqueeze(0)
        
        if src_img is not None and tgt_img is not None: break

    encoder = Encoder(args.num_features, use_sigmoid=True)
    decoder = Decoder(args.num_features)
    classifier = Classifier(7, 10)
    img_classifier = ImageClassifier(10)
    encoder.load_state_dict(torch.load(args.encoder))
    decoder.load_state_dict(torch.load(args.decoder))
    
    if args.classifier is not None:
        classifier.load_state_dict(torch.load(args.classifier))
    if args.img_classifier is not None:
        img_classifier.load_state_dict(torch.load(args.img_classifier))
 
    encoder.cuda()
    decoder.cuda()
    classifier.cuda()
    img_classifier.cuda()
    
    encoder.eval()
    decoder.eval()
    classifier.eval()
    img_classifier.eval()

    sm = nn.Softmax(dim=1)

    with torch.no_grad():
        src_z = encoder(src_img)
        tgt_z = encoder(tgt_img)

    src_cls_z = src_z[:, :7]
    tgt_cls_z = tgt_z[:, :7]
    
    src_var_z = src_z[:, 7:]
    tgt_var_z = tgt_z[:, 7:]
    
    src_cls_tgt_var_z = torch.cat((src_cls_z, tgt_var_z), dim=1)
    tgt_cls_src_var_z = torch.cat((tgt_cls_z, src_var_z), dim=1)

    sm = nn.Softmax(dim=1)
    with torch.no_grad():
        src_recon = decoder(src_z)
        tgt_recon = decoder(tgt_z)
        src_cls_tgt_var_recon = decoder(src_cls_tgt_var_z)
        tgt_cls_src_var_recon = decoder(tgt_cls_src_var_z)
        if args.reinput:
            src_cls_tgt_var_recon = decoder(encoder(src_cls_tgt_var_recon))
            tgt_cls_src_var_recon = decoder(encoder(tgt_cls_src_var_recon))


        src_conf = sm(img_classifier(src_recon))[0]
        tgt_conf = sm(img_classifier(tgt_recon))[0]
        src_cls_tgt_var_conf = sm(img_classifier(src_cls_tgt_var_recon))[0]
        tgt_cls_src_var_conf = sm(img_classifier(tgt_cls_src_var_recon))[0]

    save_imgs(src_recon, src_cls_tgt_var_recon, src_cls_tgt_var_conf, src_conf, "z_swap_src.png")
    save_imgs(tgt_recon, tgt_cls_src_var_recon, tgt_cls_src_var_conf, tgt_conf, "z_swap_tgt.png")