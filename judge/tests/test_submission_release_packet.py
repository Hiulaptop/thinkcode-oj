from django.test import SimpleTestCase, override_settings

from judge.bridge.judge_handler import (
    SubmissionData,
    SubmissionUnavailable,
    build_submission_request_packet,
    r2_problems_enabled,
    require_r2_release,
)


def _data(**overrides):
    values = dict(
        time=1,
        memory=65536,
        short_circuit=False,
        pretests_only=False,
        contest_no=None,
        attempt_no=1,
        user_id=1,
        file_only=False,
        file_size_limit=0,
        problem_version='',
        problem_sha256='',
        problem_package_key='',
    )
    values.update(overrides)
    return SubmissionData(**values)


class SubmissionReleasePacketTest(SimpleTestCase):
    def test_packet_includes_release_identity(self):
        packet = build_submission_request_packet(
            9, 'odd1out_2', 'PY3', 'print(1)',
            _data(
                problem_version='v1',
                problem_sha256='abc123',
                problem_package_key='releases/odd1out_2/v1/package.zip',
            ),
        )
        self.assertEqual(packet['problem-id'], 'odd1out_2')
        self.assertEqual(packet['problem-version'], 'v1')
        self.assertEqual(packet['problem-sha256'], 'abc123')
        self.assertEqual(packet['problem-package-key'], 'releases/odd1out_2/v1/package.zip')

    def test_packet_omits_empty_release_fields(self):
        packet = build_submission_request_packet(9, 'odd1out_2', 'PY3', 'print(1)', _data())
        self.assertNotIn('problem-version', packet)
        self.assertNotIn('problem-sha256', packet)
        self.assertNotIn('problem-package-key', packet)


class R2OnlyDispatchTest(SimpleTestCase):
    @override_settings(BRIDGED_R2_PROBLEMS=True)
    def test_missing_release_is_unavailable(self):
        with self.assertRaises(SubmissionUnavailable) as ctx:
            require_r2_release(_data())
        self.assertIn('no published R2 problem release', str(ctx.exception))

    @override_settings(BRIDGED_R2_PROBLEMS=True)
    def test_published_release_is_allowed(self):
        require_r2_release(_data(problem_sha256='abc123', problem_version='v1'))

    @override_settings(BRIDGED_R2_PROBLEMS=False)
    def test_legacy_mode_allows_missing_release(self):
        require_r2_release(_data())

    @override_settings(BRIDGED_R2_PROBLEMS=True)
    def test_r2_mode_flag(self):
        self.assertTrue(r2_problems_enabled())

    @override_settings(BRIDGED_R2_PROBLEMS=False)
    def test_legacy_mode_flag(self):
        self.assertFalse(r2_problems_enabled())
