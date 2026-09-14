import shutil
import unittest

from django.test import SimpleTestCase

from judge.utils.codeforces_polygon import (
    ImportPolygonError,
    close_unbalanced_tex_environments,
    pandoc_tex_to_markdown,
)


class CloseUnbalancedTexEnvironmentsTest(SimpleTestCase):
    def test_closes_unclosed_enumerate(self):
        tex = (
            'Given a list.\n'
            '\\begin{enumerate}\n'
            '\\item first\n'
            '\\item second\n'
        )
        out = close_unbalanced_tex_environments(tex)
        self.assertEqual(out.count('\\begin{enumerate}'), 1)
        self.assertEqual(out.count('\\end{enumerate}'), 1)
        self.assertTrue(out.rstrip().endswith('\\end{enumerate}'))

    def test_closes_nested_unclosed_environments(self):
        tex = (
            '\\begin{itemize}\n'
            '\\item outer\n'
            '\\begin{enumerate}\n'
            '\\item inner\n'
        )
        out = close_unbalanced_tex_environments(tex)
        self.assertIn('\\end{enumerate}', out)
        self.assertIn('\\end{itemize}', out)
        self.assertLess(out.rfind('\\end{enumerate}'), out.rfind('\\end{itemize}'))

    def test_leaves_balanced_tex_unchanged(self):
        tex = (
            '\\begin{enumerate}\n'
            '\\item a\n'
            '\\end{enumerate}\n'
        )
        self.assertEqual(close_unbalanced_tex_environments(tex), tex)

    def test_ignores_commented_begin(self):
        tex = 'Hello\n% \\begin{enumerate}\nworld\n'
        self.assertEqual(close_unbalanced_tex_environments(tex), tex)

    def test_ignores_begin_inside_verbatim(self):
        tex = (
            '\\begin{verbatim}\n'
            '\\begin{enumerate}\n'
            '\\end{verbatim}\n'
        )
        self.assertEqual(close_unbalanced_tex_environments(tex), tex)


@unittest.skipUnless(shutil.which('pandoc'), 'pandoc not installed')
class PandocTexToMarkdownTest(SimpleTestCase):
    def test_converts_unclosed_enumerate(self):
        tex = (
            'Given a list.\n'
            '\\begin{enumerate}\n'
            '\\item first\n'
            '\\item second\n'
        )
        md = pandoc_tex_to_markdown(tex)
        self.assertIn('first', md)
        self.assertIn('second', md)

    def test_wraps_remaining_pandoc_errors(self):
        with self.assertRaises(ImportPolygonError) as ctx:
            pandoc_tex_to_markdown('\\end{enumerate}')
        self.assertIn('pandoc failed to convert', str(ctx.exception))
