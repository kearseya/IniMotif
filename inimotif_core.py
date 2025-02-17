#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Nov 22 11:18:39 2019

@author: lcheng
"""
from Bio import SeqIO
import numpy as np
import gzip
from collections import Counter
from typing import Tuple,Set
from itertools import product, combinations

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import warnings
from scipy.stats import norm
from windows import gen_full_win_list
from yattag import Doc,indent
import warnings

from adjustText import adjust_text
import random

from dna_logo import Logo

def save_figure(file_name):
    plt.savefig(file_name,dpi=300)
    plt.close()

class KmerCounter:
    """
    general class for counting kmers from an input string

    Attributes:
        k: length of kmer
        revcom_flag: bool, counting reverse complement or not
        unique_kmer_in_seq_mode: only count unique kmer on a given input sequence
    """
    def __init__(self, k, revcom_flag=True, unique_kmer_in_seq_mode=True):
        assert k>0, "kmer length should be greater than 0"
        assert k<32, "kmer should be shorter than 32 bases"

        if k<16:
            self.dtype = np.uint32
        elif k<32:
            self.dtype = np.uint64
        else:
            print("kmer should be shorter than 32 bases")
            raise ValueError

        self.k = k
        self.revcom_flag = revcom_flag
        self.unique_kmer_in_seq_mode = unique_kmer_in_seq_mode

        base_map = {'A': 0, 'C': 1, 'G': 2, 'T': 3}
        self.base = {bk:self.dtype(base_map[bk]) for bk in base_map}
        self.revcom_dict = {'A':'T', 'C':'G', 'G':'C', 'T':'A', 'N':'N'}

        self.mask = self.gen_hash_mask(k)
        self.twobit_mask = self.dtype(3) # 0b11

        self.kmer_dict = {}
        self.top_kmers_list = None

        self.n_seq = 0
        self.n_total_kmer = 0

    # generate a hash mask for kmers such that bits out of scope can be masked to 0
    def gen_hash_mask(self,k):
        assert k<32, "kmer should be shorter than 32 bases"
        mask = self.dtype((1<<2*k)-1)
        return mask

    def kmer2hash(self, kmer):
        """
        kmer: input sequence
        return: a hash code
        """
        k = self.k
        assert self.k == len(kmer)
        assert k<32, "kmer should be shorted than 32 bases"
        kh = self.base[kmer[0]]
        for tb in kmer[1:]:
            kh = kh<<self.dtype(2)
            kh += self.base[tb]
        return kh

    def hash2kmer(self, hashkey):
        """
        hashkey: hash key of kmer, numpy
        k: length of kmer
        """
        k = self.k
        base = np.array('ACGT', 'c')
        arr = np.chararray(k)
        mask = self.twobit_mask
        arr[-1]=base[ mask & hashkey]
        for i in range(2,k+1):
            hashkey = (hashkey>>self.dtype(2))
            arr[-i]=base[mask & hashkey]
        return arr.tostring().decode("utf-8")

    # return reverse complement of input string
    def revcom(self, in_str):
        rev_in_str = in_str[::-1]
        return "".join([self.revcom_dict[c] for c in rev_in_str])

    # return reverse complement of input hash
    def revcom_hash(self, in_hash):
        com_hash = self.mask - in_hash  # complement hash
        # reverse
        ret_hash = self.twobit_mask & com_hash
        for _ in range(self.k-1):
            ret_hash = ret_hash<<self.dtype(2)
            com_hash = com_hash>>self.dtype(2)
            ret_hash += self.twobit_mask & com_hash
        return ret_hash

    # scan kmers in a sequence
    def scan_seq(self, in_str):
        in_str = in_str.upper()  # input string must be upper case
        len_str = len(in_str)
        res_dict = {}
        k = self.k
        i=0
        prev_hash = self.dtype(-1)
        while(i<=len_str-k):
            tmpstr = in_str[i:i+k]
            # omit a kmer if it contains "N"
            if "N" in tmpstr:
                i += 1 + max([pos for pos, char in enumerate(tmpstr) if char == 'N'])
                prev_hash = self.dtype(-1)
                continue
            if prev_hash==self.dtype(-1):
                tmphash = self.kmer2hash(tmpstr)
            # reuse hash in previous position
            else:
                tmphash = (prev_hash<<self.dtype(2)) & self.mask
                tmphash += self.base[ in_str[i+k-1] ]
            prev_hash = tmphash
            res_dict[tmphash] = res_dict.get(tmphash,0)+1
            i += 1
        return res_dict

    # merge the counted kmers
    def merge_res(self, kmer_dict) -> None:
        for key in kmer_dict:
            # a kmer is only counted once in a input string in kmer_dict
            val = 1 if self.unique_kmer_in_seq_mode else kmer_dict[key]
            self.kmer_dict[key] = self.kmer_dict.get(key,0) + val
            self.n_total_kmer += kmer_dict[key]

    # check if a kmer is palindrome
    def is_palindrome(self, kmer, kmer_type="string"):
        if type(kmer)==type('ACT'):
            return kmer==self.revcom(kmer)
        elif type(kmer)==type(self.mask):
            return kmer==self.revcom_hash(kmer)
        else:
            raise Exception(f'Invalid kmer type: {type(kmer)}')

    # get the combined counts for kmer and its rev. com.
    def get_pair_cnt(self, kmer_hash):
        revcom_hash = self.revcom_hash(kmer_hash)
        revcom_val = self.kmer_dict.get(revcom_hash,0)
        val = self.kmer_dict.get(kmer_hash,0)
        if kmer_hash==revcom_hash:  # palindrome
            return val
        else:
            return revcom_val+val

    # get top m kmers with the highest counts
    # return a tuple, first row is forward kmer hash of top m kmers, second row is the corresponding reverse complements hash
    def get_top_kmers(self, m=6) -> Tuple:
        assert len(self.kmer_dict)>=2*m, f"requested number of kmer {2*m} is larger than the dictionary size {len(self.kmer_dict)}"

        # # return a turple, first row is kmer_hash:count pairs, the second row is revcom_kmer_hash: count
        # def gen_res(res):
        #     kmer_hash_list = tuple( (x[0], self.kmer_dict[x[0]] ) for x in res )
        #     revcom_hash_list = tuple( (self.revcom_hash(x[0]), self.kmer_dict.get(self.revcom_hash(x[0]), 0) ) for x in res )
        #     return kmer_hash_list, revcom_hash_list

        # return a tuple, first row is forward kmer hash of top m kmers, second row is the corresponding reverse complements hash
        def gen_res(res):
            kmer_hash_list = tuple( x[0] for x in res )
            revcom_hash_list = tuple( self.revcom_hash(x[0]) for x in res )
            return kmer_hash_list, revcom_hash_list

        tmp_counter = Counter(self.kmer_dict)
        res = tmp_counter.most_common(m)
        if not self.revcom_flag:
            self.top_kmers_list = gen_res(res)
            return self.top_kmers_list

        # consider reverse complement
        ## get dictionary by summing reverse complement's counts
        def get_revcom_dict(in_dict):
            out_dict = {}
            for tmp_key in in_dict:
                tmp_val = in_dict[tmp_key]

                tmp_revcom_key = self.revcom_hash(tmp_key)
                tmp_revcom_val = self.kmer_dict.get(tmp_revcom_key,0)
                if tmp_revcom_key in out_dict:
                    continue
                if tmp_key==tmp_revcom_key:  # palindrome
                    out_dict[tmp_key] = tmp_val
                else:
                    out_dict[tmp_key] = tmp_val + tmp_revcom_val
                    out_dict[tmp_revcom_key] = 0
            return out_dict
        ## get the top 2*m kmers, from which choose the top m kmers by summing its rev. com. counts
        res = tmp_counter.most_common(2*m)
        top_dict = {x[0]:x[1] for x in res}
        top_dict = get_revcom_dict(top_dict)
        ## a top kmer must have the following minimum counts
        top_min_cnt = sorted([top_dict[k] for k in top_dict if top_dict[k]>0])[-m]
        top_min_half_cnt = top_min_cnt/2

        ## filter the dictionary by top_min_cnt
        top_dict = {k:self.kmer_dict[k] for k in self.kmer_dict if self.kmer_dict[k]>=top_min_half_cnt}
        top_dict = get_revcom_dict(top_dict)

        ## get the top m kmers from sumed dictionary
        tmp_counter = Counter(top_dict)
        res = tmp_counter.most_common(m)

        self.top_kmers_list = gen_res(res)
        return self.top_kmers_list

    # get the consensus sequence from the kmer dictionary
    def get_consensus(self, ret_string=True):
        if self.top_kmers_list:
            res = self.top_kmers_list
        else:
            res = self.get_top_kmers(1)
        kmer_hash = res[0][0]
        if ret_string:
            kmer = self.hash2kmer(kmer_hash)
            return kmer
        else:
            return kmer_hash

    # calculate hamming distance between to kmer hashes
    def cal_hamdis_hash(self, kh1, kh2):
        res = 0
        for p in range(self.k):
            tmp1 = self.twobit_mask & (kh1>> self.dtype(2*p)) 
            tmp2 = self.twobit_mask & (kh2>> self.dtype(2*p))
            res += (tmp1!=tmp2)
        return res

    # get the hamming ball
    def get_hamming_ball(self, kmer_hash, n_max_mutation=2) -> Set:
        def mutate(kmer_hash, pos):
            tmpmask = self.dtype(0)
            base_list = []
            for p in pos:
                tmpmask += (self.twobit_mask << self.dtype(2*p) )
                base_list.append(self.twobit_mask & (kmer_hash>> self.dtype(2*p) ))
            tmpbase = self.dtype((~tmpmask) & self.mask & kmer_hash)

            def my_gen(m):
                return [i for i in range(4) if i!=m]

            for e in product(*[my_gen(b) for b in base_list]):
                tmphash = tmpbase
                for i,p in enumerate(pos):
                    tmphash += (e[i]<< self.dtype(2*p) )
                yield type(self.mask)(tmphash) # also works for pos=()

        res_set = set()
        assert self.k>n_max_mutation, f"number of mutation {n_max_mutation} >= kmer length {self.k}"
        for i_mutation in range(n_max_mutation+1):
            for pos in combinations(range(self.k), i_mutation):
                # print(f'pos={pos}')
                for kh in mutate(kmer_hash, pos):
                    # print(f'add {self.hash2kmer(kh)}')
                    res_set.add(kh)
        return res_set

    def scan_file(self, file_name, file_type="fasta"):
        """
        file_name: input DNA sequence file name
        file_type: fasta, fastq,
        """
        self.n_seq = 0
        self.n_total_kmer = 0
        self.kmer_dict = {}
        self.top_kmers_list = None

        if file_name.endswith(".gz"):
            fh = gzip.open(file_name,"rt")
        else:
            fh = open(file_name, "r")

        for rec in SeqIO.parse(fh,"fasta"):
            self.n_seq += 1
            tmpdict = self.scan_seq(str(rec.seq))
            self.merge_res(tmpdict)
        fh.close()

        self.top_kmers_list = self.get_top_kmers()
        return self.kmer_dict

    # make kmer distribution plot
    # plot kmer distribution around the given consensus sequence
    def mk_kmer_dis_plot(self, consensus_seq=None, outfile=None):
        if not consensus_seq:
            consensus_seq = self.get_consensus()
        
        consensus_hash = self.kmer2hash(consensus_seq)
        revcom_consensus_hash = self.revcom_hash(consensus_hash)

        labelcolours = ['C0', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7']

        # prepare all kmers's hamming distances to consensus
        n_kmer = len(self.kmer_dict)
        all_kh_arr = np.zeros(n_kmer,dtype=self.dtype)
        all_cnt_arr = np.zeros(n_kmer,dtype="float")
        i=0
        for k,v in self.kmer_dict.items():
            all_kh_arr[i] = k
            all_cnt_arr[i] = v
            i+=1
        forward_hamdis_arr = all_cnt_arr.copy()
        revcom_hamdis_arr = all_cnt_arr.copy()
        for i,kh in enumerate(all_kh_arr):
            forward_hamdis_arr[i] = self.cal_hamdis_hash(consensus_hash, kh)
            revcom_hamdis_arr[i] = self.cal_hamdis_hash(revcom_consensus_hash, kh)
        if self.revcom_flag:
            hamdis_arr = np.minimum(forward_hamdis_arr, revcom_hamdis_arr)
        else:
            hamdis_arr = forward_hamdis_arr
        hamdis_arr += (np.random.rand(len(hamdis_arr))-0.5)*0.75

        # plot all dots
        plt.scatter(hamdis_arr, all_cnt_arr, color='0.75', alpha=0.7, s=1)

        # plot top kmers and their labels
        texts = []
        for m in range(len(self.top_kmers_list)):
            tmp_kmer_list = self.top_kmers_list[m]
            for i,kh in enumerate(tmp_kmer_list):
                tmpind = np.where(all_kh_arr==kh)[0][0]
                plt.scatter(hamdis_arr[tmpind], all_cnt_arr[tmpind], label=self.hash2kmer(kh), color=labelcolours[i], s=3)
                texts.append(plt.text(hamdis_arr[tmpind], all_cnt_arr[tmpind]-0.3, f'{self.hash2kmer(kh)} {self.kmer_dict[kh]}', color=labelcolours[i], fontsize=5))

        # adjust text
        adjust_text(texts, lw=0.5)

        # plot legend
        labels = []
        for i,kh in enumerate(self.top_kmers_list[m]):
            foward_kmer = self.hash2kmer(kh)
            revcom_kmer = self.revcom(foward_kmer)
            total_cnt = self.get_pair_cnt(kh)
            if foward_kmer==revcom_kmer:
                labels.append(f'{foward_kmer} (Palindrome) {total_cnt}')
            else:
                labels.append(f'{foward_kmer} {revcom_kmer} {total_cnt}')

        leg = plt.legend(labels, prop={'family': 'Monospace', 'size':7})
        for i,text in enumerate(leg.get_texts()):
            leg.legendHandles[i].set_color(labelcolours[i])
            text.set_color(labelcolours[i])
        
        plt.xlabel("Hamming distance (with random noise)")
        plt.ylabel("Kmer count")
        plt.title(f'Kmer length: {self.k} Seq num: {self.n_seq} Total kmers: {self.n_total_kmer}')

        save_figure(outfile)

    def disp_kmer_info(self, kmer_list=None):
        if not kmer_list:
            kmer_list = self.top_kmers_list[0]

        if self.revcom_flag:
            info_str_arr = [f'Display {len(kmer_list)} kmer pairs (kmer & reverse complement), kmer_len={self.k}.', '']
        else:
            info_str_arr = [f'Display {len(kmer_list)} kmers, kmer_len={self.k}', '']

        for e in kmer_list:
            if type(e) == type('ACG'):
                kmer = e
                khash = self.kmer2hash(kmer)
            elif type(e) == type(self.mask):
                khash = e
                kmer = self.hash2kmer(khash)
            else:
                print(f'Unkown input kmer hash type: {type(e)}, should be {type("ACG")} or {type(self.mask)}')
                raise TypeError

            palindrome_flag = self.is_palindrome(kmer)
            if palindrome_flag and self.revcom_flag:
                info_str_arr.append(f'Total count is {self.get_pair_cnt(khash)}. This is a Palindrome.')
            elif self.revcom_flag:
                info_str_arr.append( f'Total count is {self.get_pair_cnt(khash)}' )
            info_str_arr.append(f'{kmer} {self.kmer_dict[khash]}')

            if self.revcom_flag:
                rc_kmer = self.revcom(kmer)
                rc_khash = self.kmer2hash(rc_kmer)
                info_str_arr.append(f'{rc_kmer} {self.kmer_dict[rc_khash]}')

            info_str_arr.append('')

        for info_str in info_str_arr:
            print(info_str)

        return info_str_arr

class MotifManager:
    def __init__(self, kmer_counter, consensus_seq=None, n_max_mutation=2, kmer_dict=None, revcom_flag=True):
        """
        kmer_counter: a KmerCounter instance
        consensus_seq: consensus sequence, can be other sequences different to kmer_counter's
        n_max_mutation: maximum number of allowed mutation to consensus sequence
        kmer_dict: a kmer dictionary similar to kmer_counter's, could be use do find a second motif after removing kmers belonging to a first motif
        revcom_flag: if reverse complement should be counted
        """
        if not consensus_seq:
            self.consensus_seq = kmer_counter.get_consensus()
        else:
            self.consensus_seq = consensus_seq
        if not kmer_dict:
            self.kmer_dict = kmer_counter.kmer_dict
        else:
            self.kmer_dict = kmer_dict
        if n_max_mutation*4>kmer_counter.k:
            new_val = int(np.floor(kmer_counter.k/4))
            w_str = f'n_max_mutation={n_max_mutation} must be smaller than 1/4 of kmer length k={kmer_counter.k}.'+"\n"+f'Changed to n_max_mutation={new_val} now.'
            warnings.warn(w_str,UserWarning)
            n_max_mutation = new_val

        self.kmer_counter = kmer_counter
        self.n_max_mutation = n_max_mutation
        self.revcom_flag = revcom_flag

        self.consensus_hash = kmer_counter.kmer2hash(self.consensus_seq)
        self.forward_motif_ball = kmer_counter.get_hamming_ball(self.consensus_hash, n_max_mutation)
        self.con_revcom_hash = kmer_counter.revcom_hash(self.consensus_hash)
        self.revcom_motif_ball = set([kmer_counter.revcom_hash(kh) for kh in self.forward_motif_ball ])
        self.is_palindrome = self.consensus_hash==self.con_revcom_hash

        # data for motif logo construction
        if revcom_flag and not self.is_palindrome:
            self.cntarr = self.get_pair_cntarr(self.forward_motif_ball)
        else:
            self.cntarr = self.get_kmers_cntarr(self.forward_motif_ball)

        self.forward_motif_mat = self.gen_motif_cnt_mat(self.forward_motif_ball, self.cntarr)
        self.revcom_motif_mat = np.flipud(self.forward_motif_mat.copy()[:,::-1])

        # data for motif position figure
        self.bins = np.arange(0,1+0.01,0.01)
        self.tfbs_pos_dis_forward = np.zeros(len(self.bins)-1 ,dtype="float")
        self.tfbs_pos_dis_revcom = np.zeros(len(self.bins)-1,dtype="float")

        # data for number of binding sites on sequences
        self.n_tfbs_forward_arr = np.zeros(kmer_counter.n_seq, dtype="int")  # number of tfbs (forward motif) on each input sequence
        self.n_tfbs_revcom_arr = np.zeros(kmer_counter.n_seq, dtype="int")

        # number of all sequences
        self.n_seq = kmer_counter.n_seq

        # number of motif sequences
        self.n_tfbs_forward_seq = 0    # sequence contain forward motif
        self.n_tfbs_revcom_seq = 0     # sequence contain revcom motif
        self.n_tfbs_seq = 0            # sequence contain forward/revcom motif, not necessary the sum of previous two numbers

        # co-occurence of motif
        self.ff_co_occur_index = 0  # forward-forward motif co-occurence
        self.fr_co_occur_index = 0  # forward-reverse motif co-occurence

    # generate the motif count matrix, same dimension as position weight matrix (pwm)
    def gen_motif_cnt_mat(self, kmerhash_arr, cnt_arr):
        k = self.kmer_counter.k
        mat = np.zeros(shape=(k, 4), dtype="int")   #  k x 4 matrix
        for kh, kc in zip(kmerhash_arr,cnt_arr):
            for i in range(k):
                tmpbase = (kh>>self.kmer_counter.dtype(2*i)) & self.kmer_counter.twobit_mask
                mat[i, tmpbase] += kc
        return mat

    # get the combined counts for kmer and its rev. com.
    def get_pair_cnt(self, kmer_hash):
        revcom_hash = self.kmer_counter.revcom_hash(kmer_hash)
        revcom_val = self.kmer_dict.get(revcom_hash,0)
        val = self.kmer_dict.get(kmer_hash,0)
        if kmer_hash==revcom_hash:  # palindrome
            return val
        else:
            return revcom_val+val

    def get_pair_cntarr(self, kmer_arr):
        cnt_arr = np.zeros(len(kmer_arr),dtype='int')
        for i,kh in enumerate(kmer_arr):
            cnt_arr[i] = self.get_pair_cnt(kh)
        return cnt_arr

    def get_kmers_cntarr(self, kmer_arr):
        cnt_arr = np.zeros(len(kmer_arr),dtype='int')
        for i,kh in enumerate(kmer_arr):
            cnt_arr[i] = self.kmer_dict.get(kh,0)
        return cnt_arr

    # search motifs in the input sequence
    # output: first element (list) is start positions of forward motif matching the input string
    #         second element (list) is start positions of revcom motif matching the input string
    def motif_match(self, in_str) -> Tuple:
        in_str = in_str.upper()  # input string must be upper case
        len_str = len(in_str)
        k = self.kmer_counter.k

        forward_pos_list = []
        revcom_pos_list = []
        both_pos_list = []  # positions match both forward motif and revcom motif
        i=0
        prev_hash = self.kmer_counter.dtype(-1)
        while(i<=len_str-k):
            tmpstr = in_str[i:i+k]
            # omit a kmer if it contains "N"
            if "N" in tmpstr:
                i += 1 + max([pos for pos,char in enumerate(tmpstr) if char == 'N'])
                prev_hash = self.kmer_counter.dtype(-1)
                continue
            if prev_hash==self.kmer_counter.dtype(-1):
                tmphash = self.kmer_counter.kmer2hash(tmpstr)
            # reuse hash in previous position
            else:
                tmphash = (prev_hash<< self.kmer_counter.dtype(2) ) & self.kmer_counter.mask
                tmphash += self.kmer_counter.base[ in_str[i+k-1] ]
            prev_hash = tmphash
            tmpflag1, tmpflag2 = False, False
            if tmphash in self.forward_motif_ball:
                forward_pos_list.append(i)
                tmpflag1 = True
            if not self.is_palindrome and self.revcom_flag:
                if tmphash in self.revcom_motif_ball:
                    revcom_pos_list.append(i)
                    tmpflag2 = True
            if tmpflag1 and tmpflag2:
                both_pos_list.append(i)
            i += 1
        return forward_pos_list,revcom_pos_list

    def _get_style_str(self):
        style_str = """
        body {
            font-family: sans-serif, Arial, Helvetica;
        }
        p {
            word-break: break-all;
            white-space: normal;
        }
        forward{
            color: red;
        }
        revcom{
            color: blue;
        }
        overlap{
            color: green;
        }
        """
        return style_str

    def output_match_html(self, file_name, file_type="fasta", outfile="motif_match.html"):
        if file_name.endswith(".gz"):
            fh = gzip.open(file_name,"rt")
        else:
            fh = open(file_name, "r")
        style_str = self._get_style_str()
        doc, tag, text = Doc().tagtext()
        doc.asis('<!DOCTYPE html>')
        with tag('html',lang="en"):
            with tag('head'):
                with tag('title'):
                    text('Motif Sequences')
                doc.stag('meta', charset="utf-8")
                doc.stag('meta', name="viewport", content="width=device-width, initial-scale=1")
                with tag('style'):
                    text(style_str) # specify style
            with tag('body'):
                with tag('h1'):
                    text('IniMotif')
                with tag('h2'):
                    text('Sequences contain motifs')
                    doc.stag('br')
                    doc.stag('br')
                    text(f'num of maximal allowed mutations: {self.n_max_mutation}')
                    doc.stag('br')
                    text(f'forward consensus: ')
                    with tag('forward'):
                        text(self.consensus_seq)
                    doc.stag('br')
                    text(f'reverse complement: ')
                    with tag('revcom'):
                        text(self.kmer_counter.revcom(self.consensus_seq))
                    doc.stag('br')
                for rec in SeqIO.parse(fh,"fasta"):
                    tmpseq = str(rec.seq).upper()
                    fw_pos_list,rc_pos_list = self.motif_match(tmpseq)
                    if not fw_pos_list and not rc_pos_list:
                        continue
                    win_list,win_type_list = gen_full_win_list(fw_pos_list, rc_pos_list, self.kmer_counter.k, len(tmpseq))

                    with tag('p'):
                        # output header
                        text(">"+rec.id)
                        # output line break
                        doc.stag('br')
                        # output sequence
                        for win,win_type in zip(win_list, win_type_list):
                            if win_type==0:
                                text(tmpseq[win[0]:win[1]])
                            elif win_type==1:
                                with tag('forward'):
                                    text(tmpseq[win[0]:win[1]])
                            elif win_type==2:
                                with tag('revcom'):
                                    text(tmpseq[win[0]:win[1]])
                            elif win_type==3:
                                with tag('overlap'):
                                    text(tmpseq[win[0]:win[1]])
                            else:
                                warnings.warn(f'Unkown win_type={win_type}')
        fh.close()

        html_str = indent(doc.getvalue(), indent_text = True) # will also indent the text directly contained between <tag> and </tag>
        with open(outfile,'w') as out_fh:
            out_fh.write(html_str)


    # scan motif in a sequence
    def scan_seq(self, in_str, hamming_ball):
        in_str = in_str.upper()  # input string must be upper case
        len_str = len(in_str)
        k = self.kmer_counter.k

        res_list = []
        i=0
        prev_hash = self.kmer_counter.dtype(-1)
        while(i<=len_str-k):
            tmpstr = in_str[i:i+k]
            # omit a kmer if it contains "N"
            if "N" in tmpstr:
                i += 1 + max([pos for pos,char in enumerate(tmpstr) if char == 'N'])
                prev_hash = self.kmer_counter.dtype(-1)
                continue
            if prev_hash==self.kmer_counter.dtype(-1):
                tmphash = self.kmer_counter.kmer2hash(tmpstr)
            # reuse hash in previous position
            else:
                tmphash = (prev_hash<< self.kmer_counter.dtype(2) ) & self.kmer_counter.mask
                tmphash += self.kmer_counter.base[ in_str[i+k-1] ]
            prev_hash = tmphash
            if tmphash in hamming_ball:
                res_list.append(i)
            i += 1

        res_list = [e/(len_str-k) for e in res_list]  # record relative position on the string
        res = np.histogram(res_list, self.bins) # res is a tuple, res[0] are the counts, res[1] are the bins edge

        return res[0]

    def merge_res_forward(self, pos_cnt) -> None:
        self.tfbs_pos_dis_forward += pos_cnt

    def merge_res_revcom(self, pos_cnt) -> None:
        self.tfbs_pos_dis_revcom += pos_cnt

    def scan_file(self, file_name, file_type="fasta"):
        """
        file_name: input DNA sequence file name
        file_type: fasta, fastq,
        """
        if file_name.endswith(".gz"):
            fh = gzip.open(file_name,"rt")
        else:
            fh = open(file_name, "r")

        for i,rec in enumerate(SeqIO.parse(fh,"fasta")):
            tmpseq = str(rec.seq)
            tmpcnt = self.scan_seq(tmpseq, self.forward_motif_ball)
            self.merge_res_forward(tmpcnt)
            self.n_tfbs_forward_arr[i] = sum(tmpcnt)
            if self.revcom_flag and not self.is_palindrome:
                tmpcnt = self.scan_seq(tmpseq, self.revcom_motif_ball)
                self.merge_res_revcom(tmpcnt)
                self.n_tfbs_revcom_arr[i] = sum(tmpcnt)
        fh.close()

        if self.revcom_flag:
            self.n_tfbs_seq = sum( np.logical_or(self.n_tfbs_forward_arr>0, self.n_tfbs_revcom_arr>0) )
        else:
            self.n_tfbs_seq = sum( self.n_tfbs_forward_arr>0 )

        tmpn1 = sum(self.n_tfbs_forward_arr>0)
        tmpn2 = sum(self.n_tfbs_forward_arr>1) # more than 1 motifs on sequence
        self.ff_co_occur_index = tmpn2/tmpn1  # forward-forward co-occurence index

        self.n_tfbs_forward_seq = tmpn1
        self.n_tfbs_revcom_seq = sum(self.n_tfbs_revcom_arr>0)
        self.n_tfbs_seq = sum(np.logical_or( self.n_tfbs_forward_arr>0, self.n_tfbs_revcom_arr>0))

        if self.revcom_flag and not self.is_palindrome:
            tmpn1 = sum(np.logical_or( self.n_tfbs_forward_arr>0, self.n_tfbs_revcom_arr>0))
            tmpn2 = sum(np.logical_and( self.n_tfbs_forward_arr>0, self.n_tfbs_revcom_arr>0))
            self.fr_co_occur_index = tmpn2/tmpn1


    # make bubble plot for motif (forward & revcom) co-occurences
    def mk_bubble_plot(self, outfile="co_occur_fig.png") -> None:
        tfbs_arr = np.vstack((self.n_tfbs_forward_arr, self.n_tfbs_revcom_arr))
        uniq_pairs,uniq_cnt = np.unique(tfbs_arr, axis=1, return_counts=True)
        # do not display non motif sequences for better visualization
        if uniq_pairs[0,0]==0 and uniq_pairs[1,0]==0:
            uniq_pairs = uniq_pairs[:,1:]
            uniq_cnt = uniq_cnt[1:]
        plt.scatter(uniq_pairs[0,], uniq_pairs[1,], s=uniq_cnt)
        perc = round(self.n_tfbs_seq/self.n_seq*100,1)
        plt.title(f'{self.n_tfbs_seq} out of {self.n_seq} ({perc}%) sequences contain TFBS')
        plt.xlabel('Number of forward motif on sequence')
        plt.ylabel('Number of revcom motif on sequence')

        save_figure(outfile)
        # plt.savefig(outfile)
        # plt.close()
        #plt.ioff()
        #plt.show()

    # make motif logo
    # motif_mat: a k x 4 numpy array, element is the count a base in a position
    def mk_logo_plot(self, motif_mat, outfile="logo.png"):
        logo = Logo(count_mat=motif_mat, out_logo_file=outfile)
        logo.draw_logo()

    # make motif position distribution plot
    def mk_motif_posdis_plot(self, outfile="posdis.png") -> None:
        def kde_smooth(x):
            x_kde = np.linspace(0,len(x),1000)
            std = 5
            density = sum(xi*norm.pdf(x_kde, mu, std) for mu,xi in enumerate(x))
            return density/sum(density)

        # kernel smoothing
        y_sum_forward = sum(self.tfbs_pos_dis_forward)
        y_sum_revcom = sum(self.tfbs_pos_dis_revcom)
        p_forward = float(y_sum_forward)/(y_sum_forward+y_sum_revcom)
        p_revcom = 1-p_forward

        den_forward = p_forward * kde_smooth(self.tfbs_pos_dis_forward)
        if self.revcom_flag and not self.is_palindrome:
            den_revcom = p_revcom * kde_smooth(self.tfbs_pos_dis_revcom)

        x_kde = np.linspace(0,len(self.tfbs_pos_dis_forward),1000)

        plt.plot(x_kde,den_forward)
        if self.revcom_flag and not self.is_palindrome:
            plt.plot(x_kde,den_revcom)
        plt.title(f'TFBS position distribution')
        plt.xlabel('Relative position')
        plt.ylabel('Kernel density')
        if self.revcom_flag and not self.is_palindrome:
            plt.legend(('forward','revcom'))
        else:
            plt.legend(('forward'))
        
        save_figure(outfile)
        # plt.savefig(outfile)
        # plt.close()
        #plt.ioff()
        #plt.show()


# TODO: motif location on sequence
        # number of motif on sequence, done

        # using bubble plot to display the joint number of motifs, done

        # forward-forward co-occurence index, done
        # forward-revcom co-occurence index, done

        # mutation=2 is too large for small kmers, done

        # output top kmer information, done
        # output count of a given kmer information, done

        # distance between motif on sequences, etc, DONE
        # output sequences that contain motif and highlight the motifs, DONE

# from Bio.Seq import Seq
# def upper_file(file_name, file_type="fasta"):
#     """
#     file_name: input DNA sequence file name
#     file_type: fasta, fastq,
#     """
#     if file_name.endswith(".gz"):
#         fh = gzip.open(file_name,"rt")
#     else:
#         fh = open(file_name, "r")

#     outfile = file_name+".upper.fasta"
#     foh = open(outfile,'w')
#     for rec in SeqIO.parse(fh,"fasta"):
#         rec.seq = Seq(str(rec.seq).upper())
#         SeqIO.write(rec,foh,'fasta')

#     fh.close()
#     foh.close()

class Masker:
    def __init__(self):
        pass


if __name__=="__main__":

    # in_file = sys.argv[1]
    in_file = "/home/alex/Desktop/IniMotif/Data/NF1-3t"
#    in_file = "/Users/lcheng/Documents/github/IniMotif-py/gonghong/VR_AR_hg19.fasta"
#    in_file = "/Users/lcheng/Documents/github/IniMotif-py/gonghong/gz_files/VR_ERG_hg19.fasta.gz"
#    in_file = "/Users/lcheng/Documents/github/IniMotif-py/gonghong/masked_VR_AR_hg19.fasta"

    # fp = FileProcessor(in_file, out_dir="./test", kmer_len=12)

    kc6 = KmerCounter(6, revcom_flag=False)
    kc6.scan_file(in_file)

    # kc6.get_top_kmers(40)
    # kc6.disp_kmer_info()

#    top_kmer_res = kc6.get_top_kmers()
    consensus = kc6.get_consensus()
#
#    consensus = "CATGCC"
    mm =  MotifManager(kc6, consensus, n_max_mutation=0)
    # mm.scan_file(in_file)
#    KmerCounter.mk_kmer_dis_plot(kc6)
#    mm.mk_logo_plot(mm.forward_motif_mat)
    mm.output_match_html(in_file)

##    from sklearn.neighbors import KernelDensity
#    from scipy.stats import norm
#
#    x = mm.tfbs_pos_dis_forward
#    x_d = np.linspace(0,len(x),1000)
#    density = sum(xi*norm.pdf(x_d, mu, 10) for mu,xi in enumerate(x))
#    plt.fill_between(x_d, density, alpha=0.5)
#    plt.show()
#

#    mm.mk_motif_posdis_plot()

#    mm.mk_bubble_plot()

#    con_hash = kc6.kmer2hash(consensus)
#    print(f"consensus={consensus}")
#
#    hamball = kc6.get_hamming_ball(con_hash,n_max_mutation=2)
#    for kh in hamball:
#        print(kc6.hash2kmer(kh))


#    file_arr = ['VR-AR_VR-ERG_complete.fasta.gz',
#                'VR-FA1_VR-HB13_complete.fasta.gz',
#                'VR_AR_hg19.fasta.gz',
#                'VR_ERG_hg19.fasta.gz',
#                'VR_FA1_hg19.fasta.gz',
#                'VR_HB13_hg19.fasta.gz']
#    kmer_arr = ['CTATACTACGG', 'CGATACTACGG']
#    for file in file_arr:
#        in_file = "/Users/lcheng/Documents/github/IniMotif-py/gonghong/gz_files/"+file
#        kc11 = KmerCounter(11)
#        kc11.scan_file(in_file)
#
#        kh_arr = [kc11.kmer2hash(kmer) for kmer in kmer_arr]
#        cnt_arr = [kc11.get_pair_cnt(kh) for kh in kh_arr]
#        print(f'{file}  n_seq={kc11.n_seq} {kmer_arr[0]}   {cnt_arr[0]}   {kmer_arr[1]}  {cnt_arr[1]}')

#    print("\nCount all kmer mode\n")
#    for file in file_arr:
#        in_file = "/Users/lcheng/Documents/github/IniMotif-py/gonghong/gz_files/"+file
#        kc11 = KmerCounter(11,unique_kmer_in_seq_mode=False)
#        kc11.scan_file(in_file)
#
#        kh_arr = [kc11.kmer2hash(kmer) for kmer in kmer_arr]
#        cnt_arr = [kc11.get_pair_cnt(kh) for kh in kh_arr]
#        print(f'{file}  n_seq={kc11.n_total_kmer} {kmer_arr[0]}   {cnt_arr[0]}   {kmer_arr[1]}  {cnt_arr[1]}')
#

#    in_file = "/Users/lcheng/Documents/github/IniMotif-py/gonghong/TFAP2A.fasta"
#    upper_file(in_file)
