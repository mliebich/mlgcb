# Copyright 2014 Google Inc. All Rights Reserved.
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

"""Tests that walk through Course Builder pages."""

__author__ = 'Mike Gainer (mgainer@google.com)'

import urllib

from common import crypto
from controllers import sites
from models import config
from models import roles
from models import transforms
from tests.functional import actions

COURSE_NAME = 'whitelist_test'
ADMIN_EMAIL = 'admin@foo.com'
STUDENT_EMAIL = 'student@foo.com'
NONSTUDENT_EMAIL = 'student@bar.com'

STUDENT_WHITELIST = '[%s]' % STUDENT_EMAIL


class WhitelistTest(actions.TestBase):

    _course_added = False
    _whitelist = ''
    _get_environ_old = None

    @classmethod
    def setUpClass(cls):
        sites.ApplicationContext.get_environ_old = (
            sites.ApplicationContext.get_environ)
        def get_environ_new(slf):
            environ = slf.get_environ_old()
            environ['course']['now_available'] = True
            environ['course']['whitelist'] = WhitelistTest._whitelist
            return environ
        sites.ApplicationContext.get_environ = get_environ_new

    @classmethod
    def tearDownClass(cls):
        sites.ApplicationContext.get_environ = (
            sites.ApplicationContext.get_environ_old)

    def setUp(self):
        super(WhitelistTest, self).setUp()

        actions.login(ADMIN_EMAIL, is_admin=True)
        payload_dict = {
            'name': COURSE_NAME,
            'title': 'Whitelist Test',
            'admin_email': ADMIN_EMAIL}
        request = {
            'payload': transforms.dumps(payload_dict),
            'xsrf_token': crypto.XsrfTokenManager.create_xsrf_token(
                'add-course-put')}
        response = self.testapp.put('/rest/courses/item?%s' % urllib.urlencode(
            {'request': transforms.dumps(request)}), {})
        self.assertEquals(response.status_int, 200)
        sites.setup_courses('course:/%s::ns_%s, course:/:/' % (
                COURSE_NAME, COURSE_NAME))
        actions.logout()

    def tearDown(self):
        super(WhitelistTest, self).tearDown()
        sites.reset_courses()
        WhitelistTest._whitelist = ''
        config.Registry.test_overrides.clear()

    def _expect_visible(self):
        response = self.get('/explorer')
        self.assertIn('Whitelist Test', response.body)
        response = self.get('/whitelist_test/course')
        self.assertEquals(200, response.status_int)

    def _expect_invisible(self):
        response = self.get('/explorer')
        self.assertNotIn('Whitelist Test', response.body)
        response = self.get('/whitelist_test/course', expect_errors=True)
        self.assertEquals(404, response.status_int)

    def _expect_invisible_with_login_redirect(self):
        response = self.get('/explorer')
        self.assertNotIn('Whitelist Test', response.body)
        # Not quite a standard 'invisible' response - a non-logged-in
        # user will get redirected to the login page, rather than
        # just served a 404.
        response = self.get('/whitelist_test/course')
        self.assertEquals(302, response.status_int)
        self.assertIn('accounts/Login', response.location)

    def test_no_whitelist_not_logged_in(self):
        self._expect_visible()

    def test_course_whitelist_not_logged_in(self):
        WhitelistTest._whitelist = STUDENT_WHITELIST
        self._expect_invisible_with_login_redirect()

    def test_course_whitelist_as_admin(self):
        WhitelistTest._whitelist = STUDENT_WHITELIST
        actions.login(ADMIN_EMAIL, is_admin=True)
        self._expect_visible()

    def test_course_whitelist_as_nonstudent(self):
        WhitelistTest._whitelist = STUDENT_WHITELIST
        actions.login(NONSTUDENT_EMAIL)
        self._expect_invisible()

    def test_course_whitelist_as_student(self):
        WhitelistTest._whitelist = STUDENT_WHITELIST
        actions.login(STUDENT_EMAIL)
        self._expect_visible()

    def test_global_whitelist_not_logged_in(self):
        config.Registry.test_overrides[
            roles.GCB_WHITELISTED_USERS.name] = STUDENT_WHITELIST
        self._expect_invisible_with_login_redirect()

    def test_global_whitelist_as_admin(self):
        config.Registry.test_overrides[
            roles.GCB_WHITELISTED_USERS.name] = STUDENT_WHITELIST
        actions.login(ADMIN_EMAIL, is_admin=True)
        self._expect_visible()

    def test_global_whitelist_as_nonstudent(self):
        config.Registry.test_overrides[
            roles.GCB_WHITELISTED_USERS.name] = STUDENT_WHITELIST
        actions.login(NONSTUDENT_EMAIL)
        self._expect_invisible()

    def test_global_whitelist_as_student(self):
        config.Registry.test_overrides[
            roles.GCB_WHITELISTED_USERS.name] = STUDENT_WHITELIST
        actions.login(STUDENT_EMAIL)
        self._expect_visible()

    def test_course_whitelist_trumps_global_whitelist(self):
        # Global whitelist is nonblank, but only lists NONSTUDENT_EMAIL
        config.Registry.test_overrides[
            roles.GCB_WHITELISTED_USERS.name] = '[%s]' % NONSTUDENT_EMAIL

        # Course whitelist has STUDENT_EMAIL.
        WhitelistTest._whitelist = STUDENT_WHITELIST
        actions.login(STUDENT_EMAIL)

        self._expect_visible()

    def test_course_whitelist_with_multiple_entries(self):
        WhitelistTest._whitelist = (
            '[%s] ' % NONSTUDENT_EMAIL * 100 +
            '[%s] ' % STUDENT_EMAIL +
            '[%s] ' % NONSTUDENT_EMAIL * 100)
        actions.login(STUDENT_EMAIL)
        self._expect_visible()

    def test_global_whitelist_with_multiple_entries(self):
        config.Registry.test_overrides[
            roles.GCB_WHITELISTED_USERS.name] = (
            '[%s] ' % NONSTUDENT_EMAIL * 100 +
            '[%s] ' % STUDENT_EMAIL +
            '[%s] ' % NONSTUDENT_EMAIL * 100)
        actions.login(STUDENT_EMAIL)
        self._expect_visible()
