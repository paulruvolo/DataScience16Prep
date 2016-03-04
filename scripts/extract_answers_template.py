#!/usr/bin/env python
""" This script is designed to support active reading.  It takes as input
    a set of ipython notebook as well as some target cells which define a set
    of reading exercises.  The script processes the collection of notebooks
    and builds a notebook which summarizes the responses to each question.
"""

import argparse
import json
import os
import re
import sys
import urllib
from collections import OrderedDict
from copy import deepcopy
from multiprocessing import Pool
from numpy import argmin
import Levenshtein
import pandas as pd

PROJECT_DIR = os.path.relpath(os.path.join(os.path.dirname(__file__), '..'))


def read_json_from_url(url):
    """Given an URL, return its contents as JSON; or None if no JSON exists at that URL.

    Prints exceptions except 404.

    This is a global function so that it can be used as an argument to `p.map`"""

    fid = urllib.urlopen(url)
    try:
        if 200 <= fid.getcode() <= 299:
            return json.load(fid)
    except Exception as ex:
        print >> sys.stderr, "error loading {}: {}".format(url, ex)
    finally:
        fid.close()
    return None


class NotebookExtractor(object):
    """ The top-level class for extracting answers from a notebook.
        TODO: add support multiple notebooks
    """

    MATCH_THRESH = 10  # maximum edit distance to consider something a match

    def __init__(self, users_df, notebook_template_file, include_usernames=False):
        """ Initialize with the specified notebook URLs and
            list of question prompts """
        self.users_df = users_df
        self.question_prompts = self.build_question_prompts(notebook_template_file)
        self.include_usernames = include_usernames
        nb_name_full = os.path.split(notebook_template_file)[1]
        self.nb_name_stem = os.path.splitext(nb_name_full)[0]

    def build_question_prompts(self, notebook_template_file):
        """Returns a list of `QuestionPrompt`. Each cell with metadata `is_question` truthy
        produces an instance of `QuestionPrompt`."""
        with open(notebook_template_file, 'r') as fid:
            self.template = json.load(fid)

        prompts = []
        prev_prompt = None
        for idx, cell in enumerate(self.template['cells']):
            is_final_cell = idx + 1 == len(self.template['cells'])
            metadata = cell['metadata']
            if metadata.get('is_question', False):
                if prev_prompt is not None:
                    prompts[-1].stop_md = u''.join(cell['source'])
                prompts.append(QuestionPrompt(question_heading=u"",
                                              index=len(prompts),
                                              start_md=u''.join(cell['source']),
                                              stop_md=u'next_cell',
                                              is_optional=metadata.get('is_optional', None),
                                              is_poll=metadata.get('is_poll', False)
                                              ))
                if metadata.get('allow_multi_cell', False):
                    prev_prompt = prompts[-1]
                    # if it's the last cell, take everything else
                    if is_final_cell:
                        prompts[-1].stop_md = u""
                else:
                    prev_prompt = None
        return prompts

    def fetch_notebooks(self):
        """Returns a dictionary {github_username -> url, json?}.

        Unavailable notebooks have a value of None."""

        p = Pool(20)  # HTTP fetch parallelism. This number is empirically good.
        print "Retrieving %d notebooks" % self.users_df['notebook_urls'].count()
        return dict(zip(self.users_df['gh_username'],
                        p.map(read_json_from_url, self.users_df['notebook_urls'])))

    def gh_username_to_fullname(self, gh_username):
        return self.users_df[users_df['gh_username'] == gh_username]['Full Name'].iloc[0]

    def extract(self):
        """ Filter the notebook at the notebook_URL so that it only contains
            the questions and answers to the reading.
        """

        nbs = self.fetch_notebooks()
        self.usernames = sorted(self.users_df['gh_username'], key=self.gh_username_to_fullname)

        users_missing_notebooks = [u for u, notebook_content in nbs.items() if not notebook_content]
        if users_missing_notebooks:
            print "Users missing notebooks:", ', '.join(map(self.gh_username_to_fullname, users_missing_notebooks))

        if self.include_usernames:
            # Sort by username iff including the usernames in the output.
            # This makes it easier to find students.
            nbs = OrderedDict(sorted(nbs.items(), key=lambda t: t[0].lower()))

        for prompt in self.question_prompts:
            prompt.answer_status = {}
            for gh_username, notebook_content in nbs.items():
                if notebook_content is None:
                    continue
                suppress_non_answer = bool(prompt.answers)
                response_cells = \
                    prompt.get_closest_match(notebook_content['cells'],
                                             NotebookExtractor.MATCH_THRESH,
                                             suppress_non_answer)
                if not response_cells:
                    status = 'missed'
                elif not response_cells[-1]['source'] or not any(c['source'] for c in response_cells):
                    status = 'blank'
                else:
                    status = 'answered'
                    prompt.answers[gh_username] = response_cells
                prompt.answer_status[gh_username] = status

        # Report missing answers
        for prompt in self.question_prompts:
            if prompt.is_poll or prompt.is_optional:
                continue
            unanswered = sorted((username, status)
                                for username, status in prompt.answer_status.items()
                                if status != 'answered')
            for username, status in unanswered:
                print "{status} {prompt_name}: {username}".format(
                    status=status.capitalize(),
                    prompt_name=prompt.name,
                    username=self.gh_username_to_fullname(username))

        sort_responses = not self.include_usernames
        sort_responses = False  # FIXME doesn't work because questions are collected into first response
        if sort_responses:
            def cell_slines_length(response_cells):
                return len('\n'.join(u''.join(cell['source']) for cell in response_cells).strip())
            for prompt in self.question_prompts:
                prompt.answers = OrderedDict(sorted(prompt.answers.items(), key=lambda t: cell_slines_length(t[1])))

    def write_notebook(self):
        suffix = "_responses_with_names" if self.include_usernames else "_responses"
        output_file = os.path.join(PROJECT_DIR, "processed_notebooks", self.nb_name_stem + suffix + ".ipynb")
        remove_duplicate_answers = not self.include_usernames

        filtered_cells = []
        for prompt in self.question_prompts:
            answers = prompt.answers_without_duplicates if remove_duplicate_answers else prompt.answers
            for gh_username, response_cells in answers.items():
                if self.include_usernames:
                    filtered_cells.append(
                        NotebookExtractor.markdown_heading_cell(self.gh_username_to_fullname(gh_username), 4))
                filtered_cells.extend(response_cells)
        answer_book = deepcopy(self.template)
        answer_book['cells'] = filtered_cells

        print "Writing", output_file
        with open(output_file, 'wt') as fid:
            json.dump(answer_book, fid)

    def write_answer_counts(self):
        output_file = os.path.join(PROJECT_DIR, 'processed_notebooks', '%s-answer-counts.csv' % self.nb_name_stem)

        dataset = [[u in prompt.answers for u in self.usernames] for prompt in self.question_prompts]
        df = pd.DataFrame(data=dataset, columns=map(self.gh_username_to_fullname, self.usernames))
        df.index = [prompt.name for prompt in self.question_prompts]
        df.sort_index(axis=1, inplace=True)
        df['Total'] = df.sum(axis=1)
        df = pd.concat([df, pd.DataFrame(df.sum(axis=0).astype(int), columns=['Total']).T])

        print "Writing", output_file
        print 'Answer counts:'
        print df['Total']
        df.to_csv(output_file)

    @staticmethod
    def markdown_heading_cell(text, heading_level):
        """ A convenience function to return a markdown cell
            with the specified text at the specified heading_level.
            e.g. mark_down_heading_cell('Notebook Title','#')
        """
        return {u'cell_type': u'markdown',
                u'metadata': {},
                u'source': unicode('#' * heading_level + " " + text)}


class QuestionPrompt(object):
    def __init__(self, question_heading, start_md, stop_md, index=None, is_poll=False, is_optional=None):
        """ Initialize a question prompt with the specified
            starting markdown (the question), and stopping
            markdown (the markdown from the next content
            cell in the notebook).  To read to the end of the
            notebook, set stop_md to the empty string.  The
            heading to use in the summary notebook before
            the extracted responses is contined in question_heading.
            To omit the question heading, specify the empty string.
        """
        if is_optional is None and start_md:
            is_optional = bool(re.search(r'optional', start_md.split('\n')[0], re.I))
        self.question_heading = question_heading
        self.start_md = start_md
        self.stop_md = stop_md
        self.is_optional = is_optional
        self.is_poll = is_poll
        self.index = index
        self.answers = OrderedDict()

    @property
    def answers_without_duplicates(self):
        answers = dict(self.answers)
        answer_strings = set()  # answers to this question, as strings; used to avoid duplicates
        for username, response_cells in self.answers.items():
            answer_string = '\n'.join(u''.join(cell['source']) for cell in response_cells).strip()
            if answer_string in answer_strings:
                del answers[username]
            else:
                answer_strings.add(answer_string)
        return answers

    @property
    def name(self):
        m = re.match(r'^#+\s*(.+)\n', self.start_md)
        if self.question_heading:
            return self.question_heading
        format_str = {
            (False, False): '',
            (False, True): '{title}',
            (True, False): '{number}',
            (True, True): '{number}. {title}'
        }[isinstance(self.index, int), bool(m)]
        return format_str.format(number=(self.index or 0) + 1, title=m and m.group(1))

    def get_closest_match(self,
                          cells,
                          matching_threshold,
                          suppress_non_answer_cells=False):
        """ Returns a list of cells that most closely match
            the question prompt.  If no match is better than
            the matching_threshold, the empty list will be
            returned. """
        return_value = []
        distances = [Levenshtein.distance(self.start_md, u''.join(cell['source']))
                     for cell in cells]
        if min(distances) > matching_threshold:
            return return_value

        best_match = argmin(distances)
        if self.stop_md == u"next_cell":
            end_offset = 2
        elif len(self.stop_md) == 0:
            end_offset = len(cells) - best_match
        else:
            distances = [Levenshtein.distance(self.stop_md, u''.join(cell['source']))
                         for cell in cells[best_match:]]
            if min(distances) > matching_threshold:
                return return_value
            end_offset = argmin(distances)
        if len(self.question_heading) != 0 and not suppress_non_answer_cells:
            return_value.append(NotebookExtractor.markdown_heading_cell(self.question_heading, 2))
        if not suppress_non_answer_cells:
            return_value.append(cells[best_match])
        return_value.extend(cells[best_match + 1:best_match + end_offset])
        return return_value


def validate_github_username(gh_name):
    """Return `gh_name` if that Github user has a `repo_name` repository; else None."""
    fid = urllib.urlopen("http://github.com/" + gh_name)
    fid.close()
    return gh_name if 200 <= fid.getcode() <= 299 else None


def validate_github_usernames(gh_usernames, repo_name):
    """Returns a set of valid github usernames.

    A name is valid iff a GitHub user with that name exists, and owns a repository named `repo_name`.

    `gh_usernames_path` is a path to a CSV file with a `gh_username` column.

    Prints invalid names as errors."""
    p = Pool(20)
    valid_usernames = filter(None, p.map(validate_github_username, gh_usernames))
    invalid_usernames = set(gh_usernames) - set(valid_usernames)
    if invalid_usernames:
        print >> sys.stderr, "Invalid github username(s):", ', '.join(invalid_usernames)
    return valid_usernames


def get_github_user_raw_repo_url(gh_username, repo_name):
    return "https://raw.githubusercontent.com/{username}/{repo_name}".format(username=gh_username, repo_name=repo_name)


def get_github_user_notebook_url(gh_username, template_nb_path, repo_name):
    m = re.match(r'.*chap(\d+)ex.ipynb', template_nb_path)
    assert m, "template file must include chap\d+ex.ipynb"
    notebook_number = m.group(1)
    notebook_filename = "ThinkStats2/chap{}ex.ipynb".format(notebook_number)
    repo_url = get_github_user_raw_repo_url(gh_username, repo_name)
    return "{repo_url}/{branch}/{path}".format(repo_url=repo_url, branch="master", path=notebook_filename)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Summarize a set of Jupyter notebooks.')
    parser.add_argument('--repo', type=str, default='DataScience16', help='Github repository name')
    parser.add_argument('--include-usernames', action='store_true', help='include user names in the summary notebook')
    parser.add_argument('gh_users', type=str, metavar='GH_USERNAME_CSV_FILE')
    parser.add_argument('template_notebook', type=str, metavar='JUPYTER_NOTEBOOK_FILE')
    args = parser.parse_args()

    repo_name = args.repo
    users_df = pd.read_csv(args.gh_users)
    users_df['Full Name'] = users_df['First Name'].map(str) + ' ' + users_df['Last Name']

    # exit()

    valid_github_usernames = validate_github_usernames(users_df['gh_username'], repo_name)
    users_df['valid_github_repo'] = [u in valid_github_usernames for u in users_df['gh_username']]

    template_nb_path = args.template_notebook
    users_df['notebook_urls'] = [get_github_user_notebook_url(u, template_nb_path, repo_name)
                                 for u in users_df['gh_username']]
    nbe = NotebookExtractor(users_df, template_nb_path, include_usernames=args.include_usernames)
    nbe.extract()
    nbe.write_notebook()
    nbe.write_answer_counts()
