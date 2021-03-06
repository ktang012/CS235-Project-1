# kNN classification based on doc2vec


import glob
import numpy
import os
from operator import itemgetter
from sklearn.neighbors import KDTree


num_neighbors = 20
batch_size = 200  # Number of test reviews to query each time


def to_system_path(path):
    """ Convert an input path to the current system style, \ for Windows, / for others """
    if os.name == "nt":
        return path.replace("/", "\\")
    else:
        return path.replace("\\", "/")


def to_standard_path(path):
    """ Convert \ to / in path (mainly for Windows) """
    return path.replace("\\", "/")


def find_label(cnts):
    """ Find the label from a list of counts of 5 scores """
    max_cnt = 0
    idx = -1
    for i in range(0, len(cnts)):
        c = cnts[i]
        if c > max_cnt:
            max_cnt = c
            idx = i
    return idx


def get_binary_precision_recall_f1_spc(reals, preds, true_value):
    """ Compute precision, recall and f1-score for setting true_value as binary positive """
    bin_reals = []
    for label in reals:
        if label == true_value:
            bin_reals.append(True)
        else:
            bin_reals.append(False)
    bin_preds = []
    for label in preds:
        if label == true_value:
            bin_preds.append(True)
        else:
            bin_preds.append(False)
    tp = 0
    tn = 0
    fp = 0
    fn = 0
    for i in range(0, len(bin_reals)):
        real_label = bin_reals[i]
        pred_label = bin_preds[i]
        if real_label and pred_label:
            tp += 1
        elif real_label and not pred_label:
            fn += 1
        elif not real_label and pred_label:
            fp += 1
        else:
            tn += 1
    # Avoid division by zero error
    if (tp == 0) or (tn == 0) or (fp == 0) or (fn == 0):
        tp += 1
        tn += 1
        fp += 1
        fn += 1
    p = float(tp) / (tp + fp)
    r = float(tp) / (tp + fn)
    f = 2. * p * r / (p + r)
    s = float(tn) / (tn + fp)
    return p, r, f, s


def get_precision_recall_accuracy_f1_spc(reals, preds):
    """ Compute precision, recall, accuracy and f1-score for all classes """
    ps = 0
    rs = 0
    fs = 0
    ss = 0
    for i in range(1, 6):
        p, r, f, s = get_binary_precision_recall_f1_spc(reals, preds, i)
        ps += p
        rs += r
        fs += f
        ss += s
    corrects = 0
    for i in range(0, len(reals)):
        if reals[i] == preds[i]:
            corrects += 1
    return (ps / 5), (rs / 5), (float(corrects) / len(reals)), (fs / 5), (ss / 5)


dir_path = to_standard_path(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))  # Module directory
data_dir = "{0}/data".format(dir_path)
output_dir = "{0}/output-knn".format(dir_path)

if not os.path.isdir(to_system_path(output_dir)):
    os.makedirs(to_system_path(output_dir))

# This is mainly for binary version, to make two class impossible to be the same size
if num_neighbors % 2 == 0:
    num_neighbors += 1  # Make it odd

# Read number of folds dynamically
folds = []
for fp in glob.glob(to_system_path("{0}/vectors-*.npy".format(data_dir))):
    folds.append(int(os.path.basename(fp)[8:-4]))
folds.sort()

num_folds = len(folds)

# Load all review vectors and corresponding labels
doc_vecs = [None] * num_folds
labels = [None] * num_folds
for fold in folds:
    doc_vecs[fold-1] = numpy.load(to_system_path("{0}/vectors-{1}.npy".format(data_dir, fold)))

    fold_labels = []
    with open(to_system_path("{0}/labels-{1}.txt".format(data_dir, fold)), "r") as inf:
        for line in inf:
            line = line[:-1]
            if len(line) > 0:
                s = int(line)
                fold_labels.append(s)
    inf.close()
    labels[fold-1] = fold_labels
    del fold_labels
print("Document vectors and labels loaded")

# Statistics for binary version
tps = []  # True positive
tns = []  # True negative
fps = []  # False positive
fns = []  # False negative

# Statistics for multiclass version
precisions = []
recalls = []
accuracies = []
f1s = []  # F1 scores
spcs = []  # Specificities

for test_fold in folds:
    train_vecs = None
    train_labels = None

    # Construct training data
    for train_fold in folds:
        if train_fold == test_fold:
            continue

        if train_vecs is None:
            train_vecs = doc_vecs[train_fold-1]
            train_labels = labels[train_fold-1]
        else:
            train_vecs = numpy.vstack((train_vecs, doc_vecs[train_fold-1]))
            train_labels = train_labels + labels[train_fold-1]
    print("Done training data")

    tree = KDTree(train_vecs, leaf_size=2)  # KD-Tree for searching
    print("Done KD-Tree")

    actual_labels_multi = []
    actual_labels_bin = []
    predict_labels_multi = []
    predict_labels_bin = []

    test_vecs = doc_vecs[test_fold-1]
    outf = open(to_system_path("{0}/labels-{1}.tsv".format(output_dir, test_fold)), "w")

    tp = 0
    tn = 0
    fp = 0
    fn = 0

    max_round = int(float(test_vecs.shape[0]) / batch_size)

    for i in range(0, max_round):
        start_idx = i * batch_size
        end_idx = i * batch_size + batch_size

        # Query a batch of test reviews
        indices = tree.query(test_vecs[start_idx:end_idx], k=num_neighbors, return_distance=False)

        # Process every test review in the batch
        for probe in range(0, batch_size):
            actual_label = labels[test_fold - 1][probe + start_idx]
            actual_labels_multi.append(actual_label)

            cnts_multi = [0, 0, 0, 0, 0]  # Score 1, 2, 3, 4, 5
            cnts_bin = [0, 0]  # Score +, -

            for idx in indices[probe]:
                neighbor_label = train_labels[idx]
                cnts_multi[neighbor_label-1] = cnts_multi[neighbor_label-1] + 1
                if neighbor_label > 3:
                    cnts_bin[0] = cnts_bin[0] + 1
                else:
                    cnts_bin[1] = cnts_bin[1] + 1

            predict_label_multi = 1 + find_label(cnts_multi)  # Returns the index of the score
            if find_label(cnts_bin) == 0:
                predict_label_bin = "+"
            else:
                predict_label_bin = "-"

            predict_labels_multi.append(predict_label_multi)
            predict_labels_bin.append(predict_label_bin)

            if actual_label > 3:
                outf.write("{0}\t{1}\t+\t{2}\n".format(actual_label, predict_label_multi, predict_label_bin))
                if predict_label_bin == "+":
                    tp += 1
                else:
                    fn += 1
            else:
                outf.write("{0}\t{1}\t-\t{2}\n".format(actual_label, predict_label_multi, predict_label_bin))
                if predict_label_bin == "+":
                    fp += 1
                else:
                    tn += 1
        del indices
        print("Done {0} / {1}".format(i+1, max_round))
    outf.close()

    tps.append(tp)
    tns.append(tn)
    fps.append(fp)
    fns.append(fn)

    p, r, a, f, s = get_precision_recall_accuracy_f1_spc(actual_labels_multi, predict_labels_multi)
    precisions.append(p)
    recalls.append(r)
    accuracies.append(a)
    f1s.append(f)
    spcs.append(s)

    del tree, train_labels, train_vecs
    del actual_labels_multi, actual_labels_bin, predict_labels_multi, predict_labels_multi
    print("Done fold {0}".format(test_fold))


def get_precision(fold):
    """ Compute precision for the give fold """
    return float(tps[fold]) / (tps[fold] + fps[fold])


def get_recall(fold):
    """ Compute recall for the give fold """
    return float(tps[fold]) / (tps[fold] + fns[fold])


def get_specificity(fold):
    """ Compute specificity for the give fold """
    return float(tns[fold]) / (tns[fold] + fps[fold])


def get_accuracy(fold):
    """ Compute accuracy for the give fold """
    return float(tps[fold] + tns[fold]) / (tps[fold] + tns[fold] + fps[fold] + fns[fold])


def get_f1(p, r):
    """ Compute F1 score for the give fold """
    return 2. * p * r / (p + r)


def to_percentage(r):
    """ Convert a float number of percentage with 2 decimals """
    return "{:.2%}".format(r)


max_num = max(max(tps), max(tns), max(fps), max(fns))
max_len = len(str(max_num))


def to_fixed_str(n):
    """ Force converting all integers to a fixed length string (prepending spaces) """
    s = str(n)
    while len(s) < max_len:
        s = " {0}".format(s)
    return s


print("Statistics for binary version")

# Save result for binary version
outf = open(to_system_path("{0}/result_binary.txt".format(output_dir)), "w")
outf.write("TP:")
for i in range(0, num_folds):
    outf.write("  {0}".format(to_fixed_str(tps[i])))
outf.write("\nTN:")
for i in range(0, num_folds):
    outf.write("  {0}".format(to_fixed_str(tns[i])))
outf.write("\nFP:")
for i in range(0, num_folds):
    outf.write("  {0}".format(to_fixed_str(fps[i])))
outf.write("\nFN:")
for i in range(0, num_folds):
    outf.write("  {0}".format(to_fixed_str(fns[i])))
outf.write("\n\nPrecision:")
ps = []
for i in range(0, num_folds):
    t = get_precision(i)
    ps.append(t)
    outf.write("  {0}".format(to_percentage(t)))
outf.write("    {0}\nRecall:   ".format(to_percentage(sum(ps) / num_folds)))
rs = []
for i in range(0, num_folds):
    t = get_recall(i)
    rs.append(t)
    outf.write("  {0}".format(to_percentage(t)))
outf.write("    {0}\nSPC:      ".format(to_percentage(sum(rs) / num_folds)))
ss = []
for i in range(0, num_folds):
    t = get_specificity(i)
    ss.append(t)
    outf.write("  {0}".format(to_percentage(t)))
outf.write("    {0}\nAccuracy: ".format(to_percentage(sum(ss) / num_folds)))
cs = []
for i in range(0, num_folds):
    t = get_accuracy(i)
    cs.append(t)
    outf.write("  {0}".format(to_percentage(t)))
outf.write("    {0}\nF-1 Score:".format(to_percentage(sum(cs) / num_folds)))
ts = 0.
for i in range(0, num_folds):
    f1 = get_f1(ps[i], rs[i])
    ts += f1
    outf.write("  {0}".format(to_percentage(f1)))
outf.write("    {0}\n".format(to_percentage(ts / num_folds)))
outf.close()

print("Statistics for multiclass version")

# Save result for multiclass version
outf = open(to_system_path("{0}/result_multiclass.txt".format(output_dir)), "w")
outf.write("Precision:")
for i in range(0, num_folds):
    outf.write("  {0}".format(to_percentage(precisions[i])))
outf.write("    {0}\nRecall:   ".format(to_percentage(sum(precisions) / num_folds)))
for i in range(0, num_folds):
    outf.write("  {0}".format(to_percentage(recalls[i])))
outf.write("    {0}\nSPC:      ".format(to_percentage(sum(recalls) / num_folds)))
for i in range(0, num_folds):
    outf.write("  {0}".format(to_percentage(spcs[i])))
outf.write("    {0}\nAccuracy: ".format(to_percentage(sum(spcs) / num_folds)))
for i in range(0, num_folds):
    outf.write("  {0}".format(to_percentage(accuracies[i])))
outf.write("    {0}\nF-1 Score:".format(to_percentage(sum(accuracies) / num_folds)))
for i in range(0, num_folds):
    outf.write("  {0}".format(to_percentage(f1s[i])))
outf.write("    {0}\n".format(to_percentage(sum(f1s) / num_folds)))
outf.close()

print("Done")
