'''
Authors:
    Yiran Lei, Tsinghua University, leiyr20@mails.tsinghua.edu.cn
File Description:
    The script to reproduce the paper result
Last Update Time:
    2022.6.7
'''

import sys
sys.path.insert(1, './AnalysisProgram/')
from GroundTruth import *
import argparse


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='PrintQueue evaluation wrapper')
    parser.add_argument('--k', type=int, help="parameter k of PrintQueue")
    parser.add_argument('--T', type=int, help="parameter T of PrintQueue")
    parser.add_argument('--a', type=int, help="parameter alpha of PrintQueue")
    parser.add_argument('--TB', type=int, help="the number of trimmed bits of the first time window")
    parser.add_argument('--z', type=float, help="probability a cell stores a packet")
    parser.add_argument('--N', type=int, default=20, help="the number of sampled packet")
    parser.add_argument('--path', type=str, help="the path to data folder")
    parser.add_argument('--Q', type=int, nargs='+', default=[1000, 2000, 5000, 10000, 15000, 20000], help="the queue depth ranges for sampled packets")
    parser.add_argument('-TopK', action='store_true', default=False)
    args = parser.parse_args()
    print(args)
    if args.TopK:
        if not args.path:
            print("Missing parameters")
        else:
            TopK(args.path)
    else:
        if not args.path or not args.a or not args.k or not args.T or not args.TB or not args.z:
            print("Missing parameters")
        else:
            Comparison(path=args.path, alpha=args.a, k=args.k, T=args.T, TW0_TB=args.TB, TW0_z=args.z, sample_threshold=args.Q, packet_sample_number=args.N)
            DataPlaneQuery(path=args.path, alpha=args.a, k=args.k, T=args.T, TW0_TB=args.TB, TW0_z=args.z)