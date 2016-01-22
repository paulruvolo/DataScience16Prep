#!/usr/bin/env python

""" This script is designed to support active reading.  It takes as input
    a set of ipython notebook as well as some target cells which define a set
    of reading exercises.  The script processes the collection of notebooks
    and builds a notebook which summarizes the responses to each question.

    TODO:
        (1) Currently there is only support for parsing a single notebook,
            however, it will be very easy to extend this to multiple notebooks

"""

import sys
import json
from numpy import argmin
import Levenshtein
from copy import deepcopy
import pandas as pd
import urllib
import os

class NotebookExtractor(object):
    """ The top-level class for extracting answers from a notebook.
        TODO: add support multiple notebooks
    """

    MATCH_THRESH=10             # The maximum edit distance to consider something a match

    def __init__(self, notebook_URLs, question_prompts):
        """ Initialize with the specified notebook URLs and
            list of question prompts """
        self.notebook_URLs = notebook_URLs
        self.question_prompts = question_prompts

    def extract(self):
        """ Filter the notebook at the notebook_URL so that it only contains
            the questions and answers to the reading.
        """
        nbs = {}
        for url in self.notebook_URLs:
            print url
            fid = urllib.urlopen(url)
            nbs[url] = json.load(fid)
            fid.close()
        filtered_cells = []
        for i,prompt in enumerate(question_prompts):
            for url in nbs:
                filtered_cells.extend(prompt.get_closest_match(nbs[url]['cells'], NotebookExtractor.MATCH_THRESH))

        leading, nb_name_full = os.path.split(self.notebook_URLs[0])
        nb_name_stem, extension = os.path.splitext(nb_name_full)

        fid = open(nb_name_stem + "_responses.ipynb",'wt')

        answer_book = deepcopy(nbs[self.notebook_URLs[0]])
        answer_book['cells'] = filtered_cells
        json.dump(answer_book, fid)
        fid.close()

    @staticmethod
    def markdown_heading_cell(text, heading_level):
        """ A convenience function to return a markdown cell
            with the specified text at the specified heading_level.
            e.g. mark_down_heading_cell('Notebook Title','#')
        """
        return {u'cell_type':u'markdown',u'metadata':{},u'source':unicode(heading_level + " " + text)}

class QuestionPrompt(object):
    def __init__(self, question_heading, start_md, stop_md):
        """ Initialize a question prompt with the specified
            starting markdown (the question), and stopping
            markdown (the markdown from the next content
            cell in the notebook).  To read to the end of the
            notebook, set stop_md to the empty string.  The
            heading to use in the summary notebook before
            the extracted responses is contined in question_heading.
            To omit the question heading, specify the empty string.
        """
        self.question_heading = question_heading
        self.start_md = start_md
        self.stop_md = stop_md

    def get_closest_match(self, cells, matching_threshold):
        """ Returns a list of cells that most closely match
            the question prompt.  If no match is better than
            the matching_threshold, the empty list will be
            returned. """
        return_value = []
        distances = [Levenshtein.distance(self.start_md, u''.join(cell['source'])) for cell in cells]
        if min(distances) > matching_threshold:
            return return_value

        best_match = argmin(distances)
        if len(self.stop_md) == 0:
            end_offset = len(cells) - best_match
        else:
            distances = [Levenshtein.distance(self.stop_md, u''.join(cell['source'])) for cell in cells[best_match:]]
            if min(distances) > matching_threshold:
                return return_value
            end_offset = argmin(distances)
        if len(self.question_heading) != 0:
            return_value.append(NotebookExtractor.markdown_heading_cell(self.question_heading,'##'))
        return_value.append(cells[best_match])
        return_value.extend(cells[best_match+1:best_match+end_offset])
        return return_value

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print "USAGE: ./extract_answers.py ipynb-url problem_set"
        sys.exit(-1)
    question_prompts = []
    if sys.argv[2] == "1":
        question_prompts.append(QuestionPrompt(u"Question 1",
                                               u"""Print value counts for <tt>prglngth</tt> and compare to results published in the [codebook](http://www.icpsr.umich.edu/nsfg6/Controller?displayPage=labelDetails&fileCode=PREG&section=A&subSec=8016&srtLabel=611931)""",
                                               u"""Print value counts for <tt>agepreg</tt> and compare to results published in the [codebook](http://www.icpsr.umich.edu/nsfg6/Controller?displayPage=labelDetails&fileCode=PREG&section=A&subSec=8016&srtLabel=611935).

Looking at this data, please remember my comments in the book about the obligation to approach data with consideration for the context and respect for the respondents."""))

        question_prompts.append(QuestionPrompt(u"Question 2",
                                               u"""Print value counts for <tt>agepreg</tt> and compare to results published in the [codebook](http://www.icpsr.umich.edu/nsfg6/Controller?displayPage=labelDetails&fileCode=PREG&section=A&subSec=8016&srtLabel=611935).

Looking at this data, please remember my comments in the book about the obligation to approach data with consideration for the context and respect for the respondents.""",
                                               u"""Compute the mean birthweight."""))
        question_prompts.append(QuestionPrompt(u"Question 3",
                                               u"""Create a new column named <tt>totalwgt_kg</tt> that contains birth weight in kilograms.  Compute its mean.  Remember that when you create a new column, you have to use dictionary syntax, not dot notation.""",
                                               u"""Look through the codebook and find a variable, other than the ones mentioned in the book, that you find interesting.  Compute values counts, means, or other statistics."""))
        question_prompts.append(QuestionPrompt(u"Question 4",
                                               u"""Look through the codebook and find a variable, other than the ones mentioned in the book, that you find interesting.  Compute values counts, means, or other statistics.""",
                                               u"""Create a boolean Series."""))
        question_prompts.append(QuestionPrompt(u"Question 5",
                                               u'Count the number of live births with <tt>birthwgt_lb</tt> between 9 and 95 pounds (including both).  The result should be 798 ',
                                               u'Use <tt>birthord</tt> to select the records for first babies and others.  How many are there of each?'))
        question_prompts.append(QuestionPrompt(u"Question 6",
                                               u'Compute the mean <tt>prglngth</tt> for first babies and others.  Compute the difference in means, expressed in hours.',
                                               u"""## Clarifying Questions

Use this space to ask questions regarding the content covered in the reading. These questions should be restricted to helping you better understand the material. For questions that push beyond what is in the reading, use the next answer field. If you don't have a fully formed question, but are generally having a difficult time with a topic, you can indicate that here as well."""))
        question_prompts.append(QuestionPrompt(u"",
                                               u"""## Clarifying Questions

Use this space to ask questions regarding the content covered in the reading. These questions should be restricted to helping you better understand the material. For questions that push beyond what is in the reading, use the next answer field. If you don't have a fully formed question, but are generally having a difficult time with a topic, you can indicate that here as well.""",
                                               u"""## Enrichment Questions

Use this space to ask any questions that go beyond (but are related to) the material presented in this reading. Perhaps there is a particular topic you'd like to see covered in more depth. Perhaps you'd like to know how to use a library in a way that wasn't show in the reading. One way to think about this is what additional topics would you want covered in the next class (or addressed in a followup e-mail to the class). I'm a little fuzzy on what stuff will likely go here, so we'll see how things evolve."""))
        question_prompts.append(QuestionPrompt(u"",
                                               u"""## Enrichment Questions

Use this space to ask any questions that go beyond (but are related to) the material presented in this reading. Perhaps there is a particular topic you'd like to see covered in more depth. Perhaps you'd like to know how to use a library in a way that wasn't show in the reading. One way to think about this is what additional topics would you want covered in the next class (or addressed in a followup e-mail to the class). I'm a little fuzzy on what stuff will likely go here, so we'll see how things evolve.""",
                                               u"""## Additional Resources / Explorations

If you found any useful resources, or tried some useful exercises that you'd like to report please do so here. Let us know what you did, what you learned, and how others can replicate it."""))
        question_prompts.append(QuestionPrompt(u"",
                                               u"""## Additional Resources / Explorations

If you found any useful resources, or tried some useful exercises that you'd like to report please do so here. Let us know what you did, what you learned, and how others can replicate it.""",
                                               u""))

    if not question_prompts:
        print "Unknown problem set"
        sys.exit(-1)

    turnin_data = pd.read_csv(sys.argv[1])
    notebooks = turnin_data['Link to your ipython notebook']
    nbe = NotebookExtractor(notebooks, question_prompts)
    nbe.extract()