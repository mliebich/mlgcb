# coding: utf-8
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for modules/dashboard/analytics."""

__author__ = 'Julia Oh(juliaoh@google.com)'

import datetime
import os
import time

import actions
from actions import assert_contains
from actions import assert_does_not_contain
from actions import assert_equals
from mapreduce.lib.pipeline import pipeline

import appengine_config
from common import utils as common_utils
from controllers import sites
from controllers import utils
from models import config
from models import courses
from models import jobs
from models import models
from models import transforms
from models.progress import ProgressStats
from models.progress import UnitLessonCompletionTracker
from modules.data_source_providers import rest_providers
from modules.data_source_providers import synchronous_providers
from modules.mapreduce import mapreduce_module


class AnalyticsTabsWithNoJobs(actions.TestBase):

    def tearDown(self):
        config.Registry.test_overrides.clear()

    def test_blank_students_tab_no_mr(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        self.get('dashboard?action=analytics&tab=students')

    def test_blank_questions_tab_no_mr(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        self.get('dashboard?action=analytics&tab=questions')

    def test_blank_assessments_tab_no_mr(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        self.get('dashboard?action=analytics&tab=assessments')

    def test_blank_peer_review_tab_no_mr(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        self.get('dashboard?action=analytics&tab=peer_review')

    def test_blank_students_tab_with_mr(self):
        config.Registry.test_overrides[
            mapreduce_module.GCB_ENABLE_MAPREDUCE_DETAIL_ACCESS.name] = True
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        self.get('dashboard?action=analytics&tab=students')

    def test_blank_questions_tab_with_mr(self):
        config.Registry.test_overrides[
            mapreduce_module.GCB_ENABLE_MAPREDUCE_DETAIL_ACCESS.name] = True
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        self.get('dashboard?action=analytics&tab=questions')

    def test_blank_assessments_tab_with_mr(self):
        config.Registry.test_overrides[
            mapreduce_module.GCB_ENABLE_MAPREDUCE_DETAIL_ACCESS.name] = True
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        self.get('dashboard?action=analytics&tab=assessments')

    def test_blank_peer_review_tab_with_mr(self):
        config.Registry.test_overrides[
            mapreduce_module.GCB_ENABLE_MAPREDUCE_DETAIL_ACCESS.name] = True
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        self.get('dashboard?action=analytics&tab=peer_review')


class ProgressAnalyticsTest(actions.TestBase):
    """Tests the progress analytics page on the Course Author dashboard."""

    EXPECTED_TASK_COUNT = 3

    def enable_progress_tracking(self):
        config.Registry.test_overrides[
            utils.CAN_PERSIST_ACTIVITY_EVENTS.name] = True

    def test_empty_student_progress_stats_analytics_displays_nothing(self):
        """Test analytics page on course dashboard when no progress stats."""

        # The admin looks at the analytics page on the board to check right
        # message when no progress has been recorded.

        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        response = self.get('dashboard?action=analytics&tab=students')
        assert_contains(
            'Google &gt;<a href="%s"> ' % self.canonicalize('dashboard') +
            'Dashboard </a>&gt; Analytics &gt; Students', response.body)
        assert_contains('have not been calculated yet', response.body)

        response = response.forms[
            'gcb-generate-analytics-data'].submit().follow()
        assert len(self.taskq.GetTasks('default')) == (
            ProgressAnalyticsTest.EXPECTED_TASK_COUNT)

        assert_contains('is running', response.body)

        self.execute_all_deferred_tasks()

        response = self.get(response.request.url)
        assert_contains('were last updated at', response.body)
        assert_contains('currently enrolled: 0', response.body)
        assert_contains('total: 0', response.body)

        assert_contains('Student Progress', response.body)
        assert_contains(
            'No student progress has been recorded for this course.',
            response.body)
        actions.logout()

    def test_student_progress_stats_analytics_displays_on_dashboard(self):
        """Test analytics page on course dashboard."""

        self.enable_progress_tracking()

        student1 = 'student1@google.com'
        name1 = 'Test Student 1'
        student2 = 'student2@google.com'
        name2 = 'Test Student 2'

        # Student 1 completes a unit.
        actions.login(student1)
        actions.register(self, name1)
        actions.view_unit(self)
        actions.logout()

        # Student 2 completes a unit.
        actions.login(student2)
        actions.register(self, name2)
        actions.view_unit(self)
        actions.logout()

        # Admin logs back in and checks if progress exists.
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        response = self.get('dashboard?action=analytics&tab=students')
        assert_contains(
            'Google &gt;<a href="%s"> ' % self.canonicalize('dashboard') +
            'Dashboard </a>&gt; Analytics &gt; Students', response.body)
        assert_contains('have not been calculated yet', response.body)

        response = response.forms[
            'gcb-generate-analytics-data'].submit().follow()
        assert len(self.taskq.GetTasks('default')) == (
            ProgressAnalyticsTest.EXPECTED_TASK_COUNT)

        response = self.get('dashboard?action=analytics')
        assert_contains('is running', response.body)

        self.execute_all_deferred_tasks()

        response = self.get('dashboard?action=analytics')
        assert_contains('were last updated at', response.body)
        assert_contains('currently enrolled: 2', response.body)
        assert_contains('total: 2', response.body)

        assert_contains('Student Progress', response.body)
        assert_does_not_contain(
            'No student progress has been recorded for this course.',
            response.body)
        # JSON code for the completion statistics.
        assert_contains(
            '\\"u.1.l.1\\": {\\"progress\\": 0, \\"completed\\": 2}',
            response.body)
        assert_contains(
            '\\"u.1\\": {\\"progress\\": 2, \\"completed\\": 0}',
            response.body)

    def test_analytics_are_individually_cancelable_and_runnable(self):
        """Test run/cancel controls for individual analytics jobs."""

        # Submit all analytics.
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        response = self.get('dashboard?action=analytics&tab=peer_review')
        response = response.forms[
            'gcb-generate-analytics-data'].submit().follow()

        # Ensure that analytics appear to be running and have cancel buttons.
        assert_contains('is running', response.body)
        assert_contains('Cancel Statistic Calculation', response.body)

        # Now that all analytics are pending, ensure that we do _not_ have
        # an update-all button.
        with self.assertRaises(KeyError):
            response = response.forms['gcb-generate-analytics-data']

        # Click the cancel button for one of the slower jobs.
        response = response.forms[
            'gcb-cancel-visualization-peer_review'].submit().follow()

        # Verify that page shows job was canceled.
        assert_contains('error updating peer review statistics', response.body)
        assert_contains('Canceled by ' + email, response.body)

        # We should now have our update-statistics button back.
        self.assertIsNotNone(response.forms['gcb-generate-analytics-data'])

        # Should also have a button to run the canceled job; click that.
        response = response.forms[
            'gcb-run-visualization-peer_review'].submit().follow()

        # All jobs should now again be running, and update-all button gone.
        with self.assertRaises(KeyError):
            response = response.forms['gcb-generate-analytics-data']

    def test_cancel_map_reduce(self):
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        response = self.get('dashboard?action=analytics&tab=peer_review')
        response = response.forms[
            'gcb-run-visualization-peer_review'].submit().follow()

        # Launch 1st stage of map/reduce job; we must do this in order to
        # get the pipeline woken up enough to have built a root pipeline
        # record.  Without this, we do not have an ID to use when canceling.
        self.execute_all_deferred_tasks(iteration_limit=1)

        # Cancel the job.
        response = response.forms[
            'gcb-cancel-visualization-peer_review'].submit().follow()
        assert_contains('Canceled by ' + email, response.body)

        # Now permit any pending tasks to complete, and expect the job's
        # status message to remain at "Canceled by ...".
        #
        # If the cancel didn't take effect, the map/reduce should have run to
        # completion and the job's status would change to completed, changing
        # the message.  This is verified in
        # model_jobs.JobOperationsTest.test_killed_job_can_still_complete
        self.execute_all_deferred_tasks()
        response = self.get(response.request.url)
        assert_contains('Canceled by ' + email, response.body)

    def test_get_entity_id_wrapper_in_progress_works(self):
        """Tests get_entity_id wrappers in progress.ProgressStats."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        progress_stats = ProgressStats(course)
        unit1 = course.add_unit()

        # pylint: disable-msg=protected-access
        assert_equals(
            progress_stats._get_unit_ids_of_type_unit(), [unit1.unit_id])
        assessment1 = course.add_assessment()
        assert_equals(
            progress_stats._get_assessment_ids(), [assessment1.unit_id])
        lesson11 = course.add_lesson(unit1)
        lesson12 = course.add_lesson(unit1)
        assert_equals(
            progress_stats._get_lesson_ids(unit1.unit_id),
            [lesson11.lesson_id, lesson12.lesson_id])
        lesson11.has_activity = True
        course.set_activity_content(lesson11, u'var activity=[]', [])
        assert_equals(
            progress_stats._get_activity_ids(unit1.unit_id, lesson11.lesson_id),
            [0])
        assert_equals(
            progress_stats._get_activity_ids(unit1.unit_id, lesson12.lesson_id),
            [])

    def test_get_entity_label_wrapper_in_progress_works(self):
        """Tests get_entity_label wrappers in progress.ProgressStats."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        progress_stats = ProgressStats(course)
        unit1 = course.add_unit()

        # pylint: disable-msg=protected-access
        assert_equals(
            progress_stats._get_unit_label(unit1.unit_id),
            'Unit %s' % unit1.index)
        assessment1 = course.add_assessment()
        assert_equals(
            progress_stats._get_assessment_label(assessment1.unit_id),
            assessment1.title)
        lesson11 = course.add_lesson(unit1)
        lesson12 = course.add_lesson(unit1)
        assert_equals(
            progress_stats._get_lesson_label(unit1.unit_id, lesson11.lesson_id),
            lesson11.index)
        lesson11.has_activity = True
        course.set_activity_content(lesson11, u'var activity=[]', [])
        assert_equals(
            progress_stats._get_activity_label(
                unit1.unit_id, lesson11.lesson_id, 0), 'L1.1')
        assert_equals(
            progress_stats._get_activity_label(
                unit1.unit_id, lesson12.lesson_id, 0), 'L1.2')
        lesson12.objectives = """
            <question quid="123" weight="1" instanceid=1></question>
            random_text
            <gcb-youtube videoid="Kdg2drcUjYI" instanceid="VD"></gcb-youtube>
            more_random_text
            <question-group qgid="456" instanceid=2></question-group>
            yet_more_random_text
        """
        cpt_ids = progress_stats._get_component_ids(
            unit1.unit_id, lesson12.lesson_id, 0)
        self.assertEqual(set([u'1', u'2']), set(cpt_ids))

    def test_compute_entity_dict_constructs_dict_correctly(self):
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        progress_stats = ProgressStats(course)
        course_dict = progress_stats.compute_entity_dict('course', [])
        assert_equals(course_dict, {
            'label': 'UNTITLED COURSE', 'u': {}, 's': {}})

    def test_compute_entity_dict_constructs_dict_for_empty_course_correctly(
        self):
        """Tests correct entity_structure is built."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        unit1 = course.add_unit()
        assessment1 = course.add_assessment()
        progress_stats = ProgressStats(course)
        # pylint: disable-msg=g-inconsistent-quotes
        assert_equals(
            progress_stats.compute_entity_dict('course', []),
            {'label': 'UNTITLED COURSE', 'u': {unit1.unit_id: {
                'label': 'Unit %s' % unit1.index, 'l': {}}}, 's': {
                    assessment1.unit_id: {'label': assessment1.title}}})
        lesson11 = course.add_lesson(unit1)
        assert_equals(
            progress_stats.compute_entity_dict('course', []),
            {
                "s": {
                    assessment1.unit_id: {
                        "label": assessment1.title
                    }
                },
                "u": {
                    unit1.unit_id: {
                        "l": {
                            lesson11.lesson_id: {
                                "a": {},
                                "h": {
                                    0: {
                                        "c": {},
                                        "label": "L1.1"
                                    }
                                },
                                "label": lesson11.index
                            }
                        },
                        "label": "Unit %s" % unit1.index
                    }
                },
                'label': 'UNTITLED COURSE'
            })
        lesson11.objectives = """
            <question quid="123" weight="1" instanceid="1"></question>
            random_text
            <gcb-youtube videoid="Kdg2drcUjYI" instanceid="VD"></gcb-youtube>
            more_random_text
            <question-group qgid="456" instanceid="2"></question-group>
            yet_more_random_text
        """
        assert_equals(
            progress_stats.compute_entity_dict('course', []),
            {
                "s": {
                    assessment1.unit_id: {
                        "label": assessment1.title
                    }
                },
                "u": {
                    unit1.unit_id: {
                        "l": {
                            lesson11.lesson_id: {
                                "a": {},
                                "h": {
                                    0: {
                                        "c": {
                                            u'1': {
                                                "label": "L1.1.1"
                                            },
                                            u'2': {
                                                "label": "L1.1.2"
                                            }
                                        },
                                        "label": "L1.1"
                                    }
                                },
                                "label": lesson11.index
                            }
                        },
                        "label": "Unit %s" % unit1.index
                    }
                },
                "label": 'UNTITLED COURSE'
            })


class QuestionAnalyticsTest(actions.TestBase):
    """Tests the question analytics page from Course Author dashboard."""

    def _enable_activity_tracking(self):
        config.Registry.test_overrides[
            utils.CAN_PERSIST_ACTIVITY_EVENTS.name] = True

    def _get_sample_v15_course(self):
        """Creates a course with different types of questions and returns it."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        unit1 = course.add_unit()
        lesson1 = course.add_lesson(unit1)
        assessment_old = course.add_assessment()
        assessment_old.title = 'Old assessment'
        assessment_new = course.add_assessment()
        assessment_new.title = 'New assessment'
        assessment_peer = course.add_assessment()
        assessment_peer.title = 'Peer review assessment'

        # Create a multiple choice question.
        mcq_new_id = 1
        mcq_new_dict = {
            'description': 'mcq_new',
            'type': 0,  # Multiple choice question.
            'choices': [{
                'text': 'answer',
                'score': 1.0
            }],
            'version': '1.5'
        }
        mcq_new_dto = models.QuestionDTO(mcq_new_id, mcq_new_dict)

        # Create a short answer question.
        frq_new_id = 2
        frq_new_dict = {
            'defaultFeedback': '',
            'rows': 1,
            'description': 'short answer',
            'hint': '',
            'graders': [{
                'matcher': 'case_insensitive',
                'score': '1.0',
                'response': 'hi',
                'feedback': ''
            }],
            'question': 'short answer question',
            'version': '1.5',
            'type': 1,  # Short answer question.
            'columns': 100
        }
        frq_new_dto = models.QuestionDTO(frq_new_id, frq_new_dict)

        # Save these questions to datastore.
        models.QuestionDAO.save_all([mcq_new_dto, frq_new_dto])

        # Create a question group.
        question_group_id = 3
        question_group_dict = {
            'description': 'question_group',
            'items': [
                {'question': str(mcq_new_id)},
                {'question': str(frq_new_id)},
                {'question': str(mcq_new_id)}
            ],
            'version': '1.5',
            'introduction': ''
        }
        question_group_dto = models.QuestionGroupDTO(
            question_group_id, question_group_dict)

        # Save the question group to datastore.
        models.QuestionGroupDAO.save_all([question_group_dto])

        # Add a MC question and a question group to leesson1.
        lesson1.objectives = """
            <question quid="1" weight="1" instanceid="QN"></question>
            random_text
            <gcb-youtube videoid="Kdg2drcUjYI" instanceid="VD"></gcb-youtube>
            more_random_text
            <question-group qgid="3" instanceid="QG"></question-group>
        """

        # Add a MC question, a short answer question, and a question group to
        # new style assessment.
        assessment_new.html_content = """
            <question quid="1" weight="1" instanceid="QN2"></question>
            <question quid="2" weight="1" instanceid="FRQ2"></question>
            random_text
            <gcb-youtube videoid="Kdg2drcUjYI" instanceid="VD"></gcb-youtube>
            more_random_text
            <question-group qgid="3" instanceid="QG2"></question-group>
        """

        return course

    def test_get_summarized_question_list_from_event(self):
        """Tests the transform functions per event type."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])

        question_aggregator = (synchronous_providers.QuestionStatsGenerator
                               .MultipleChoiceQuestionAggregator(course))

        event_payloads = open(os.path.join(
            appengine_config.BUNDLE_ROOT,
            'tests/unit/common/event_payloads.json')).read()

        event_payload_dict = transforms.loads(event_payloads)
        for event_info in event_payload_dict.values():
            # pylint: disable-msg=protected-access
            questions = question_aggregator._process_event(
                event_info['event_source'], event_info['event_data'])
            assert_equals(questions, event_info['transformed_dict_list'])

    def test_compute_question_stats_on_empty_course_returns_empty_dicts(self):

        sites.setup_courses('course:/test::ns_test, course:/:/')
        app_context = sites.get_all_courses()[0]

        question_stats_computer = (
            synchronous_providers.QuestionStatsGenerator(app_context))
        id_to_questions, id_to_assessments = question_stats_computer.run()
        assert_equals({}, id_to_questions)
        assert_equals({}, id_to_assessments)

    def test_id_to_question_dict_constructed_correctly(self):
        """Tests id_to_question dicts are constructed correctly."""
        course = self._get_sample_v15_course()
        tracker = UnitLessonCompletionTracker(course)
        assert_equals(
            tracker.get_id_to_questions_dict(),
            {
                'u.1.l.2.c.QN': {
                    'answer_counts': [0],
                    'label': 'Unit 1 Lesson 1, Question mcq_new',
                    'location': 'unit?unit=1&lesson=2',
                    'num_attempts': 0,
                    'score': 0
                },
                'u.1.l.2.c.QG.i.0': {
                    'answer_counts': [0],
                    'label': ('Unit 1 Lesson 1, Question Group question_group '
                              'Question mcq_new'),
                    'location': 'unit?unit=1&lesson=2',
                    'num_attempts': 0,
                    'score': 0
                },
                'u.1.l.2.c.QG.i.2': {
                    'answer_counts': [0],
                    'label': ('Unit 1 Lesson 1, Question Group question_group '
                              'Question mcq_new'),
                    'location': 'unit?unit=1&lesson=2',
                    'num_attempts': 0,
                    'score': 0
                }
            }
        )
        assert_equals(
            tracker.get_id_to_assessments_dict(),
            {
                's.4.c.QN2': {
                    'answer_counts': [0],
                    'label': 'New assessment, Question mcq_new',
                    'location': 'assessment?name=4',
                    'num_attempts': 0,
                    'score': 0
                },
                's.4.c.QG2.i.0': {
                    'answer_counts': [0],
                    'label': ('New assessment, Question Group question_group '
                              'Question mcq_new'),
                    'location': 'assessment?name=4',
                    'num_attempts': 0,
                    'score': 0
                },
                's.4.c.QG2.i.2': {
                    'answer_counts': [0],
                    'label': ('New assessment, Question Group question_group '
                              'Question mcq_new'),
                    'location': 'assessment?name=4',
                    'num_attempts': 0,
                    'score': 0
                }
            }
        )


COURSE_ONE = 'course_one'
COURSE_TWO = 'course_two'


class CronCleanupTest(actions.TestBase):
    # pylint: disable-msg=protected-access

    def setUp(self):
        super(CronCleanupTest, self).setUp()
        admin_email = 'admin@foo.com'
        self.course_one = actions.simple_add_course(
            COURSE_ONE, admin_email, 'Course One')
        self.course_two = actions.simple_add_course(
            COURSE_TWO, admin_email, 'Course Two')

        actions.login(admin_email, True)
        actions.register(self, admin_email, COURSE_ONE)
        actions.register(self, admin_email, COURSE_TWO)

        self.save_tz = os.environ.get('TZ')
        os.environ['TZ'] = 'GMT'
        time.tzset()

    def tearDown(self):
        if self.save_tz:
            os.environ['TZ'] = self.save_tz
        else:
            del os.environ['TZ']
        time.tzset()

    def _clean_jobs(self, max_age):
        return mapreduce_module.CronMapreduceCleanupHandler._clean_mapreduce(
            max_age)

    def _get_num_root_jobs(self, course_name):
        with common_utils.Namespace('ns_' + course_name):
            return len(pipeline.get_root_list()['pipelines'])

    def _force_finalize(self, job):
        # For reasons that I do not grok, running the deferred task list
        # until it empties out in test mode does not wind up marking the
        # root job as 'done'.  (Whereas when running the actual service,
        # the job does get marked 'done'.)  This has already cost me most
        # of two hours of debugging, and I'm no closer to figuring out why,
        # much less having a monkey-patch into the Map/Reduce or Pipeline
        # libraries that would correct this.  Cleaner to just transition
        # the job into a completed state manually.
        root_pipeline_id = jobs.MapReduceJob.get_root_pipeline_id(job.load())
        with common_utils.Namespace(job._namespace):
            p = pipeline.Pipeline.from_id(root_pipeline_id)
            context = pipeline._PipelineContext('', 'default', '')
            context.transition_complete(p._pipeline_key)

    def test_non_admin_cannot_cleanup(self):
        actions.login('joe_user@foo.com')
        response = self.get('/cron/mapreduce/cleanup', expect_errors=True)
        self.assertEquals(400, response.status_int)

    def test_admin_cleanup_gets_200_ok(self):
        response = self.get('/cron/mapreduce/cleanup', expect_errors=True)
        self.assertEquals(200, response.status_int)

    def test_no_jobs_no_cleanup(self):
        self.assertEquals(0, self._clean_jobs(datetime.timedelta(seconds=0)))

    def test_unstarted_job_not_cleaned(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()

        self.assertEquals(1, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(0, self._clean_jobs(datetime.timedelta(minutes=1)))

    def test_active_job_not_cleaned(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()
        self.execute_all_deferred_tasks(iteration_limit=1)

        self.assertEquals(1, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(0, self._clean_jobs(datetime.timedelta(minutes=1)))

    def test_completed_job_is_not_cleaned(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()
        self.execute_all_deferred_tasks()
        self._force_finalize(mapper)

        self.assertEquals(1, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(0, self._clean_jobs(datetime.timedelta(minutes=1)))

    def test_terminated_job_with_no_start_time_is_cleaned(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()
        self.execute_all_deferred_tasks(iteration_limit=1)
        mapper.cancel()
        self.execute_all_deferred_tasks()

        self.assertEquals(1, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(1, self._clean_jobs(datetime.timedelta(minutes=1)))

        self.execute_all_deferred_tasks(iteration_limit=1)
        self.assertEquals(0, self._get_num_root_jobs(COURSE_ONE))

    def test_incomplete_job_cleaned_if_time_expired(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()
        self.execute_all_deferred_tasks(iteration_limit=1)

        self.assertEquals(1, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(1, self._clean_jobs(datetime.timedelta(seconds=0)))

        self.execute_all_deferred_tasks()  # Run deferred deletion task.
        self.assertEquals(0, self._get_num_root_jobs(COURSE_ONE))

    def test_completed_job_cleaned_if_time_expired(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()
        self.execute_all_deferred_tasks()

        self.assertEquals(1, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(1, self._clean_jobs(datetime.timedelta(seconds=0)))

        self.execute_all_deferred_tasks()  # Run deferred deletion task.
        self.assertEquals(0, self._get_num_root_jobs(COURSE_ONE))

    def test_multiple_runs_cleaned(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        for _ in range(0, 3):
            mapper.submit()
            self.execute_all_deferred_tasks()

        self.assertEquals(3, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(3, self._clean_jobs(datetime.timedelta(seconds=0)))

        self.execute_all_deferred_tasks()  # Run deferred deletion task.
        self.assertEquals(0, self._get_num_root_jobs(COURSE_ONE))

    def test_cleanup_modifies_incomplete_status(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()
        self.execute_all_deferred_tasks(iteration_limit=1)

        self.assertEquals(jobs.STATUS_CODE_STARTED, mapper.load().status_code)

        self.assertEquals(1, self._clean_jobs(datetime.timedelta(seconds=0)))
        self.assertEquals(jobs.STATUS_CODE_FAILED, mapper.load().status_code)
        self.assertIn('assumed to have failed', mapper.load().output)

    def test_cleanup_does_not_modify_completed_status(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()
        self.execute_all_deferred_tasks()

        self.assertEquals(jobs.STATUS_CODE_COMPLETED, mapper.load().status_code)

        self.assertEquals(1, self._clean_jobs(datetime.timedelta(seconds=0)))
        self.assertEquals(jobs.STATUS_CODE_COMPLETED, mapper.load().status_code)

    def test_cleanup_in_multiple_namespaces(self):
        mapper_one = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper_two = rest_providers.LabelsOnStudentsGenerator(self.course_two)
        for _ in range(0, 2):
            mapper_one.submit()
            mapper_two.submit()
            self.execute_all_deferred_tasks()

        self.assertEquals(2, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(2, self._get_num_root_jobs(COURSE_TWO))
        self.assertEquals(4, self._clean_jobs(datetime.timedelta(seconds=0)))

        self.execute_all_deferred_tasks()  # Run deferred deletion task.
        self.assertEquals(0, self._get_num_root_jobs(COURSE_ONE))
        self.assertEquals(0, self._get_num_root_jobs(COURSE_TWO))

    def test_cleanup_handler(self):
        mapper = rest_providers.LabelsOnStudentsGenerator(self.course_one)
        mapper.submit()
        self.execute_all_deferred_tasks(iteration_limit=1)
        mapper.cancel()
        self.execute_all_deferred_tasks()

        self.assertEquals(1, self._get_num_root_jobs(COURSE_ONE))

        # Check that hitting the cron handler via GET works as well.
        # Note that since the actual handler uses a max time limit of
        # a few days, we need to set up a canceled job which, having
        # no defined start-time will be cleaned up immediately.
        self.get('/cron/mapreduce/cleanup')

        self.execute_all_deferred_tasks(iteration_limit=1)
        self.assertEquals(0, self._get_num_root_jobs(COURSE_ONE))
