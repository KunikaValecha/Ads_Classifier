import utils
import random
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from scipy.sparse import lil_matrix
from sklearn.feature_extraction.text import TfidfTransformer

# Performs classification using RandomForest classifier.

FREQ_DIST_FILE = 'train-processed-freqdist.pkl'
BI_FREQ_DIST_FILE = 'train-processed-freqdist-bi.pkl'
TRAIN_PROCESSED_FILE = 'train-processed.csv'
TEST_PROCESSED_FILE = 'test-processed.csv'
TRAIN = False
UNIGRAM_SIZE = 15000
VOCAB_SIZE = UNIGRAM_SIZE
USE_BIGRAMS = True
if USE_BIGRAMS:
    BIGRAM_SIZE = 10000
    VOCAB_SIZE = UNIGRAM_SIZE + BIGRAM_SIZE
FEAT_TYPE = 'presence'


def get_feature_vector(CONTENTS):
    uni_feature_vector = []
    bi_feature_vector = []
    words = CONTENTS.split()
    for i in xrange(len(words) - 1):
        word = words[i]
        next_word = words[i + 1]
        if unigrams.get(word):
            uni_feature_vector.append(word)
        if USE_BIGRAMS:
            if bigrams.get((word, next_word)):
                bi_feature_vector.append((word, next_word))
    if len(words) >= 1:
        if unigrams.get(words[-1]):
            uni_feature_vector.append(words[-1])
    return uni_feature_vector, bi_feature_vector


def extract_features(CONTENT, batch_size=500, test_file=True, feat_type='presence'):
    num_batches = int(np.ceil(len(CONTENT) / float(batch_size)))
    for i in xrange(num_batches):
        batch = CONTENT[i * batch_size: (i + 1) * batch_size]
        features = lil_matrix((batch_size, VOCAB_SIZE))
        labels = np.zeros(batch_size)
        for j, CONTENTS in enumerate(batch):
            if test_file:
                CONTENT_words = CONTENTS[1][0]
                CONTENT_bigrams = CONTENTS[1][1]
            else:
                CONTENT_words = CONTENTS[2][0]
                CONTENT_bigrams = CONTENTS[2][1]
                labels[j] = CONTENTS[1]
            if feat_type == 'presence':
                CONTENT_words = set(CONTENT_words)
                CONTENT_bigrams = set(CONTENT_bigrams)
            for word in CONTENT_words:
                idx = unigrams.get(word)
                if idx:
                    features[j, idx] += 1
            if USE_BIGRAMS:
                for bigram in CONTENT_bigrams:
                    idx = bigrams.get(bigram)
                    if idx:
                        features[j, UNIGRAM_SIZE + idx] += 1
        yield features, labels


def apply_tf_idf(X):
    transformer = TfidfTransformer(smooth_idf=True, sublinear_tf=True, use_idf=True)
    transformer.fit(X)
    return transformer


def process_CONTENT(csv_file, test_file=True):
    """Returns a list of tuples of type (CONTENT_id, feature_vector)
            or (tweet_id, sentiment, feature_vector)

    Args:
        csv_file (str): Name of processed csv file generated by preprocess.py
        test_file (bool, optional): If processing test file

    Returns:
        list: Of tuples
    """
    CONTENT = []
    print 'Generating feature vectors'
    with open(csv_file, 'r') as csv:
        lines = csv.readlines()
        total = len(lines)
        for i, line in enumerate(lines):
            if test_file:
                CONTENT_id, CONTENTS = line.split(',')
            else:
                CONTENT_id, sentiment, CONTENTS = line.split(',')
            feature_vector = get_feature_vector(CONTENTS)
            if test_file:
                CONTENT.append((CONTENT_id, feature_vector))
            else:
                CONTENT.append((CONTENT_id, int(sentiment), feature_vector))
            utils.write_status(i + 1, total)
    print '\n'
    return CONTENT


if __name__ == '__main__':
    np.random.seed(1337)
    unigrams = utils.top_n_words(FREQ_DIST_FILE, UNIGRAM_SIZE)
    if USE_BIGRAMS:
        bigrams = utils.top_n_bigrams(BI_FREQ_DIST_FILE, BIGRAM_SIZE)
    CONTENT= process_CONTENT(TRAIN_PROCESSED_FILE, test_file=False)
    if TRAIN:
        train_CONTENT, val_CONTENT = utils.split_data(CONTENT)
    else:
        random.shuffle(CONTENT)
        train_CONTENT = CONTENT
    del CONTENT
    print 'Extracting features & training batches'
    clf = RandomForestClassifier(n_jobs=2, random_state=0)
    batch_size = len(train_CONTENT)
    i = 1
    n_train_batches = int(np.ceil(len(train_CONTENT) / float(batch_size)))
    for training_set_X, training_set_y in extract_features(train_CONTENT, test_file=False, feat_type=FEAT_TYPE, batch_size=batch_size):
        utils.write_status(i, n_train_batches)
        i += 1
        if FEAT_TYPE == 'frequency':
            tfidf = apply_tf_idf(training_set_X)
            training_set_X = tfidf.transform(training_set_X)
        clf.fit(training_set_X, training_set_y)
    print '\n'
    print 'Testing'
    if TRAIN:
        correct, total = 0, len(val_CONTENT)
        i = 1
        batch_size = len(val_CONTENT)
        n_val_batches = int(np.ceil(len(val_CONTENT) / float(batch_size)))
        for val_set_X, val_set_y in extract_features(val_CONTENT, test_file=False, feat_type=FEAT_TYPE, batch_size=batch_size):
            if FEAT_TYPE == 'frequency':
                val_set_X = tfidf.transform(val_set_X)
            prediction = clf.predict(val_set_X)
            correct += np.sum(prediction == val_set_y)
            utils.write_status(i, n_val_batches)
            i += 1
        print '\nCorrect: %d/%d = %.4f %%' % (correct, total, correct * 100. / total)
    else:
        del train_CONTENT
        test_CONTENT = process_CONTENT(TEST_PROCESSED_FILE, test_file=True)
        n_test_batches = int(np.ceil(len(test_CONTENT) / float(batch_size)))
        predictions = np.array([])
        print 'Predicting batches'
        i = 1
        for test_set_X, _ in extract_features(test_CONTENT, test_file=True, feat_type=FEAT_TYPE):
            if FEAT_TYPE == 'frequency':
                test_set_X = tfidf.transform(test_set_X)
            prediction = clf.predict(test_set_X)
            predictions = np.concatenate((predictions, prediction))
            utils.write_status(i, n_test_batches)
            i += 1
        predictions = [(str(j), int(predictions[j]))
                       for j in range(len(test_CONTENT))]
        utils.save_results_to_csv(predictions, 'randomforest.csv')
        print '\nSaved to randomforest.csv'
