#!/usr/bin/env python

import sys
import json
from numpy import argmin
import Levenshtein
from copy import deepcopy
import urllib
import os

MATCH_THRESH=10

def markdown_heading_cell(text, heading_level):
    return {u'cell_type':u'markdown',u'metadata':{},u'source':unicode(heading_level + " " + text)}

if len(sys.argv) < 3:
    print "USAGE: ./extract_answers.py ipynb-url problem_set_index_(starting_from_0)"
    sys.exit(-1)

print sys.argv[1]
fid = urllib.urlopen(sys.argv[1])
nb = json.load(fid)
fid.close()
cells = nb['cells']

problem_prompts_all = []
problem_prompts_all.append([
                            {'start' : u'Count the number of live births with <tt>birthwgt_lb</tt> between 9 and 95 pounds (including both).  The result should be 798 ', 'end': u'Use <tt>birthord</tt> to select the records for first babies and others.  How many are there of each?'},
                            {'start' : u'Compute the mean <tt>prglngth</tt> for first babies and others.  Compute the difference in means, expressed in hours.', 'end':u''},
                            {'omit_heading' : True,
                             'start' : u"""## Clarifying Questions

Use this space to ask questions regarding the content covered in the reading. These questions should be restricted to helping you better understand the material. For questions that push beyond what is in the reading, use the next answer field. If you don't have a fully formed question, but are generally having a difficult time with a topic, you can indicate that here as well.""", 'end':u"""## Enrichment Questions

Use this space to ask any questions that go beyond (but are related to) the material presented in this reading. Perhaps there is a particular topic you'd like to see covered in more depth. Perhaps you'd like to know how to use a library in a way that wasn't show in the reading. One way to think about this is what additional topics would you want covered in the next class (or addressed in a followup e-mail to the class). I'm a little fuzzy on what stuff will likely go here, so we'll see how things evolve."""},
                            {'omit_heading' : True,
                             'start' : u"""## Enrichment Questions

Use this space to ask any questions that go beyond (but are related to) the material presented in this reading. Perhaps there is a particular topic you'd like to see covered in more depth. Perhaps you'd like to know how to use a library in a way that wasn't show in the reading. One way to think about this is what additional topics would you want covered in the next class (or addressed in a followup e-mail to the class). I'm a little fuzzy on what stuff will likely go here, so we'll see how things evolve.""",'end':u"""## Additional Resources / Explorations

If you found any useful resources, or tried some useful exercises that you'd like to report please do so here. Let us know what you did, what you learned, and how others can replicate it."""},
                            {'omit_heading' : True,
                             'start' : u"""## Additional Resources / Explorations

If you found any useful resources, or tried some useful exercises that you'd like to report please do so here. Let us know what you did, what you learned, and how others can replicate it.""",'end':u""}])
problem_prompts_all.append([
                            {'start': u"Make a histogram of <tt>age_r</tt>, the respondent's age at the time of interview.",'end': u"Make a histogram of <tt>numfmhh</tt>, the number of people in the respondent's household."},
                            {'start' : u"Make a histogram of <tt>numfmhh</tt>, the number of people in the respondent's household.",'end':u"Make a histogram of <tt>parity</tt>, the number children the respondent has borne.  How would you describe this distribution?"},
                            {'start' : u"Make a histogram of <tt>parity</tt>, the number children the respondent has borne.  How would you describe this distribution?", 'end': u"Use Hist.Largest to find the largest values of <tt>parity</tt>."},
                            {'start' : u"Use Hist.Largest to find the largest values of <tt>parity</tt>.", 'end': u"Use <tt>totincr</tt> to select the respondents with the highest income.  Compute the distribution of <tt>parity</tt> for just the high income respondents."},
                            {'start' : u"Use <tt>totincr</tt> to select the respondents with the highest income.  Compute the distribution of <tt>parity</tt> for just the high income respondents.", 'end':u"Find the largest parities for high income respondents."},
                            {'start' : u"Find the largest parities for high income respondents.", 'end': u"Compare the mean <tt>parity</tt> for high income respondents and others."},
                            {'start' : u"Compare the mean <tt>parity</tt> for high income respondents and others.", 'end' : u"Investigate any other variables that look interesting."},
                            {'start' : u"Investigate any other variables that look interesting.", 'end': u""}
                           ])

problem_prompts = problem_prompts_all[int(sys.argv[2])]

filtered_cells = []
for i,prompt in enumerate(problem_prompts):
    distances = [Levenshtein.distance(prompt['start'], u''.join(cell['source'])) for cell in cells]
    #print min(distances)
    if min(distances) > MATCH_THRESH:
        continue

    best_match = argmin(distances)
    if len(prompt['end']) == 0:
        end_offset = len(cells) - best_match
    else:
        end_offset = argmin([Levenshtein.distance(prompt['end'], u''.join(cell['source'])) for cell in cells[best_match:]])
    if ('omit_heading' not in prompt) or prompt['omit_heading'] == False:
        filtered_cells.append(markdown_heading_cell('Question ' + str(i+1),'##'))
    filtered_cells.append(cells[best_match])
    filtered_cells.extend(cells[best_match+1:best_match+end_offset])

leading, nb_name_full = os.path.split(sys.argv[1])
nb_name_stem, extension = os.path.splitext(nb_name_full)

fid = open(nb_name_stem + "_responses.ipynb",'wt')

answer_book = deepcopy(nb)
answer_book['cells'] = filtered_cells
json.dump(answer_book, fid)
fid.close()