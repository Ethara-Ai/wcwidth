#!/usr/bin/env python
"""
A terminal browser, similar to less(1) for testing printable width of unicode.

This displays the full range of unicode points for 1 or 2-character wide
ideograms, with pipes ('|') that should always align for any terminal that
supports utf-8.

Interactive Keys:
  Navigation:
    k, y, UP          Scroll backward 1 line
    j, e, ENTER, DOWN Scroll forward 1 line
    f, SPACE, PGDOWN  Scroll forward 1 page
    b, PGUP           Scroll backward 1 page
    F, SHIFT-DOWN     Scroll forward 10 pages
    B, SHIFT-UP       Scroll backward 10 pages
    HOME              Go to top
    G, END            Go to bottom
    Ctrl-L            Refresh screen

  Mode Switching:
    0                 Exit VS mode (return to normal mode)
    1                 Narrow width (normal) / Narrow base filter (VS mode)
    2                 Wide width (normal) / Wide base filter (VS mode)
    5                 Switch to VS-15 mode (text style)
    6                 Switch to VS-16 mode (emoji style)
    c                 Toggle combining character mode
    w                 Toggle with/without variation selector (VS mode only)

  Display Adjustment:
    -, _              Decrease character name display length by 2
    +, =              Increase character name display length by 2
    v                 Select Unicode version

  Exit:
    q, Q              Quit browser

Note:
  Only one of --combining, --vs15, or --vs16 can be used at a time.
  The --without-vs option only applies when using --vs15 or --vs16.

  In VS mode, the display shows:
    - W/VS: Characters displayed with variation selector
    - WO/VS: Base characters displayed without variation selector
"""
# pylint: disable=C0103,W0622
#         Invalid constant name "echo"
#         Invalid constant name "flushout" (col 4)
#         Invalid module name "wcwidth-browser"

# std imports
import os
import sys
import signal
import string
import argparse
import functools
import unicodedata

# 3rd party
import blessed

# local
from wcwidth import ZERO_WIDTH, wcwidth, list_versions, _wcmatch_version

#: print function alias, does not end with line terminator.
echo = functools.partial(print, end='')
flushout = functools.partial(print, end='', flush=True)

#: printable length of highest unicode character description
LIMIT_UCS = 0x3fffd
UCS_PRINTLEN = len(f'{LIMIT_UCS:0x}')


def readline(term, width):
    """A rudimentary readline implementation."""
    pass


class WcWideCharacterGenerator:
    """Generator yields unicode characters of the given ``width``."""

    # pylint: disable=R0903
    #         Too few public methods (0/2)
    def __init__(self, width, unicode_version):
        """
        Class constructor.

        :param width: generate characters of given width.
        :param str unicode_version: Unicode Version for render.
        :type width: int
        """
        self.characters = (
            chr(idx) for idx in range(LIMIT_UCS)
            if wcwidth(chr(idx), unicode_version=unicode_version) == width)

    def __iter__(self):
        """Special method called by iter()."""
        return self

    def __next__(self):
        """Special method called by next()."""
        while True:
            ucs = next(self.characters)
            try:
                name = string.capwords(unicodedata.name(ucs))
            except ValueError:
                continue
            return (ucs, name)


class WcCombinedCharacterGenerator:
    """Generator yields unicode characters with combining."""

    # pylint: disable=R0903
    #         Too few public methods (0/2)

    def __init__(self, width, unicode_version):
        """
        Class constructor.

        :param int width: generate characters of given width.
        :param str unicode_version: Unicode version.
        """
        self.characters = []
        letters_o = ('o' * width)
        for (begin, end) in ZERO_WIDTH[_wcmatch_version(unicode_version)]:
            for val in [_val for _val in
                        range(begin, end + 1)
                        if _val <= LIMIT_UCS]:
                self.characters.append(
                    letters_o[:1] +
                    chr(val) +
                    letters_o[wcwidth(chr(val)) + 1:])
        self.characters.reverse()

    def __iter__(self):
        """Special method called by iter()."""
        return self

    def __next__(self):
        """
        Special method called by next().

        :return: unicode character and name, as tuple.
        :rtype: tuple[unicode, unicode]
        :raises StopIteration: no more characters
        """
        while True:
            if not self.characters:
                raise StopIteration
            ucs = self.characters.pop()
            try:
                name = string.capwords(unicodedata.name(ucs[1]))
            except ValueError:
                continue
            return (ucs, name)


class WcVariationSequenceGenerator:
    """Generator yields emoji variation sequences from emoji-variation-sequences.txt."""

    # pylint: disable=R0903
    #         Too few public methods (0/2)

    def __init__(self, base_width, unicode_version, variation_selector='VS15'):
        """
        Class constructor.

        :param int base_width: filter by base character width (1 or 2).
        :param str unicode_version: Unicode version.
        :param str variation_selector: 'VS15' or 'VS16'.
        """
        self.sequences = []

        # Determine which variation selector we're looking for
        vs_hex = 'FE0E' if variation_selector == 'VS15' else 'FE0F'

        # Find the emoji-variation-sequences.txt file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        filepath = os.path.join(script_dir, '..', 'tests', 'emoji-variation-sequences.txt')

        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                # Skip comments and empty lines
                if line.startswith('#') or not line.strip():
                    continue

                # Only process lines with our target variation selector
                if vs_hex not in line:
                    continue

                # Parse line format: "0023 FE0E  ; text style;  # (1.1) NUMBER SIGN"
                parts = line.split(';')
                if len(parts) < 2:
                    continue

                codepoints = parts[0].strip().split()
                if len(codepoints) < 2:
                    continue

                try:
                    base_cp = int(codepoints[0], 16)
                    vs_cp = int(codepoints[1], 16)
                except ValueError:
                    continue

                # Check base character width matches our filter
                if wcwidth(chr(base_cp), unicode_version=unicode_version) != base_width:
                    continue

                # Extract name from comment
                comment_parts = line.split('#')
                if len(comment_parts) >= 2:
                    # Format: "# (1.1) NUMBER SIGN"
                    name_part = comment_parts[1].strip()
                    # Remove version info like "(1.1) "
                    if ')' in name_part:
                        name = name_part.split(')', 1)[1].strip()
                    else:
                        name = name_part
                    name = string.capwords(name)
                else:
                    name = "UNKNOWN"

                # Create the variation sequence
                sequence = chr(base_cp) + chr(vs_cp)
                self.sequences.append((sequence, name))

        self.sequences.reverse()

    def __iter__(self):
        """Special method called by iter()."""
        return self

    def __next__(self):
        """
        Special method called by next().

        :return: variation sequence and name, as tuple.
        :rtype: tuple[str, str]
        :raises StopIteration: no more sequences
        """
        if not self.sequences:
            raise StopIteration
        return self.sequences.pop()


class Style:
    """Styling decorator class instance for terminal output."""

    # pylint: disable=R0903
    #         Too few public methods (0/2)
    @staticmethod
    def attr_major(text):
        """Non-stylized callable for "major" text, for non-ttys."""
        pass

    @staticmethod
    def attr_minor(text):
        """Non-stylized callable for "minor" text, for non-ttys."""
        pass

    delimiter = '|'
    continuation = ' $'
    header_hint = '-'
    header_fill = '='
    name_len = 10
    alignment = 'right'

    def __init__(self, **kwargs):
        """
        Class constructor.

        Any given keyword arguments are assigned to the class attribute of the same name.
        """
        for key, val in kwargs.items():
            setattr(self, key, val)


class Screen:
    """Represents terminal style, data dimensions, and drawables."""

    intro_msg_fmt = ('Delimiters ({delim}) should align, '
                     'unicode version is {version}.')

    def __init__(self, term, style, wide=2):
        """Class constructor."""
        self.term = term
        self.style = style
        self.wide = wide

    @property
    def header(self):
        """Text of joined segments producing full heading."""
        pass

    @property
    def hint_width(self):
        """Width of a column segment."""
        pass

    @property
    def head_item(self):
        """Text of a single column heading."""
        pass

    def msg_intro(self, version):
        """Introductory message disabled above heading."""
        pass

    @property
    def row_ends(self):
        """Bottom of page."""
        pass

    @property
    def num_columns(self):
        """Number of columns displayed."""
        pass

    @property
    def num_rows(self):
        """Number of rows displayed."""
        pass

    @property
    def row_begins(self):
        """Top row displayed for content."""
        pass

    @property
    def page_size(self):
        """Number of unicode text displayed per page."""
        pass


class Pager:
    """A less(1)-like browser for browsing unicode characters."""
    # pylint: disable=too-many-instance-attributes

    #: screen state for next draw method(s).
    STATE_CLEAN, STATE_DIRTY, STATE_REFRESH = 0, 1, 2

    def __init__(self, term, screen, character_factory, variation_selector=None,
                 show_variation_selector=True):
        """
        Class constructor.

        :param term: blessed Terminal class instance.
        :type term: blessed.Terminal
        :param screen: Screen class instance.
        :type screen: Screen
        :param character_factory: Character factory generator.
        :type character_factory: callable returning iterable.
        :param variation_selector: Variation selector mode ('VS15', 'VS16', or None).
        :type variation_selector: str or None
        :param show_variation_selector: Whether to display variation selector in VS mode.
        :type show_variation_selector: bool
        """
        self.term = term
        self.screen = screen
        self.character_factory = character_factory
        self.variation_selector = variation_selector
        self.show_variation_selector = show_variation_selector
        self.base_width_filter = screen.wide  # For VS mode filtering
        self.unicode_version = 'auto'
        self.dirty = self.STATE_REFRESH
        self.last_page = 0
        self._page_data = list()

    def on_resize(self, *args):
        """Signal handler callback for SIGWINCH."""
        pass

    def _set_lastpage(self):
        """Calculate value of class attribute ``last_page``."""
        pass

    def display_initialize(self):
        """Display 'please wait' message, and narrow build warning."""
        pass

    def initialize_page_data(self):
        """Initialize the page data for the given screen."""
        pass

    def page_data(self, idx, offset):
        """
        Return character data for page of given index and offset.

        :param idx: page index.
        :type idx: int
        :param offset: scrolling region offset of current page.
        :type offset: int
        :returns: list of tuples in form of ``(ucs, name)``
        :rtype: list[(unicode, unicode)]
        """
        pass

    def _run_notty(self, writer):
        """Pager run method for terminals that are not a tty."""
        pass

    def _run_tty(self, writer, reader):
        """Pager run method for terminals that are a tty."""
        pass

    def run(self, writer, reader):
        """
        Pager entry point.

        In interactive mode (terminal is a tty), run until
        ``process_keystroke()`` detects quit keystroke ('q').  In
        non-interactive mode, exit after displaying all unicode points.

        :param writer: callable writes to output stream, receiving unicode.
        :type writer: callable
        :param reader: callable reads keystrokes from input stream, sending
                       instance of blessed.keyboard.Keystroke.
        :type reader: callable
        """
        pass

    def process_keystroke(self, inp, idx, offset):
        """
        Process keystroke ``inp``, adjusting screen parameters.

        :param inp: return value of blessed.Terminal.inkey().
        :type inp: blessed.keyboard.Keystroke
        :param idx: page index.
        :type idx: int
        :param offset: scrolling region offset of current page.
        :type offset: int
        :returns: tuple of next (idx, offset).
        :rtype: (int, int)
        """
        pass

    def _process_keystroke_commands(self, inp):
        """Process keystrokes that issue commands (side effects)."""
        pass

    def _process_keystroke_movement(self, inp, idx, offset):
        """Process keystrokes that adjust index and offset."""
        pass

    def draw(self, writer, idx, offset):
        """
        Draw the current page view to ``writer``.

        :param callable writer: callable writes to output stream, receiving unicode.
        :param int idx: current page index.
        :param int offset: scrolling region offset of current page.
        :returns: tuple of next (idx, offset).
        :rtype: (int, int)
        """
        pass

    def draw_heading(self, writer):
        """
        Conditionally redraw screen when ``dirty`` attribute is valued REFRESH.

        When Pager attribute ``dirty`` is ``STATE_REFRESH``, cursor is moved
        to (0,0), screen is cleared, and heading is displayed.

        :param callable writer: callable writes to output stream, receiving unicode.
        :return: True if class attribute ``dirty`` is ``STATE_REFRESH``.
        :rtype: bool
        """
        pass

    def mode_label(self):
        """
        Return a label describing the current browsing mode.

        :return: Mode label string.
        :rtype: str
        """
        pass

    def draw_status(self, writer, idx):
        """
        Conditionally draw status bar when output terminal is a tty.

        :param callable writer: callable writes to output stream, receiving unicode.
        :param int idx: current page position index.
        :type idx: int
        """
        pass

    def page_view(self, data):
        """
        Generator yields text to be displayed for the current unicode pageview.

        :param list[(unicode, unicode)] data: The current page's data as tuple
            of ``(ucs, name)``.
        :returns: generator for full-page text for display
        """
        pass

    def text_entry(self, ucs, name):
        """
        Display a single column segment row describing ``(ucs, name)``.

        :param str ucs: target unicode point character string.
        :param str name: name of unicode point.
        :return: formatted text for display.
        :rtype: unicode
        """
        pass


def validate_args(opts):
    """Validate result of parse_args() and return keyword arguments for main()."""
    if opts['--wide'] is None:
        opts['--wide'] = 2
    else:
        assert opts['--wide'] in ("1", "2"), opts['--wide']
    if opts['--alignment'] is None:
        opts['--alignment'] = 'left'
    else:
        assert opts['--alignment'] in ('left', 'right'), opts['--alignment']
    opts['--wide'] = int(opts['--wide'])

    # Ensure mutual exclusivity of --combining, --vs15, and --vs16
    exclusive_opts = [opts.get('--combining', False),
                      opts.get('--vs15', False),
                      opts.get('--vs16', False)]
    assert sum(bool(opt) for opt in exclusive_opts) <= 1, \
        "Only one of --combining, --vs15, or --vs16 can be used"

    # Set character factory and variation selector
    opts['character_factory'] = WcWideCharacterGenerator
    opts['variation_selector'] = None
    opts['base_width_filter'] = opts['--wide']  # Save base width filter
    opts['display_width'] = opts['--wide']  # Default display width
    opts['show_variation_selector'] = not opts.get('--without-vs', False)

    if opts.get('--combining'):
        opts['character_factory'] = WcCombinedCharacterGenerator
    elif opts.get('--vs15'):
        opts['variation_selector'] = 'VS15'
        # Display width depends on whether showing with or without VS
        if opts['show_variation_selector']:
            opts['display_width'] = 1  # VS-15 displays at width 1
        else:
            opts['display_width'] = opts['base_width_filter']  # Use base width
    elif opts.get('--vs16'):
        opts['variation_selector'] = 'VS16'
        # Display width depends on whether showing with or without VS
        if opts['show_variation_selector']:
            opts['display_width'] = 2  # VS-16 displays at width 2
        else:
            opts['display_width'] = opts['base_width_filter']  # Use base width

    return opts


def main(opts):
    """Program entry point."""
    term = blessed.Terminal()
    style = Style()

    # if the terminal supports colors, use a Style instance with some
    # standout colors (magenta, cyan).
    if term.number_of_colors:
        style = Style(attr_major=term.magenta,
                      attr_minor=term.bright_cyan,
                      alignment=opts['--alignment'])
    style.name_len = 10

    screen = Screen(term, style, wide=opts['display_width'])
    pager = Pager(term, screen, opts['character_factory'],
                  variation_selector=opts['variation_selector'],
                  show_variation_selector=opts['show_variation_selector'])

    # Set base width filter from command-line argument
    if opts['variation_selector']:
        pager.base_width_filter = opts['base_width_filter']

    with term.location(), term.cbreak(), \
            term.fullscreen(), term.hidden_cursor():
        pager.run(writer=echo, reader=term.inkey)
    return 0


def parse_args():
    """Parse command-line arguments using argparse."""
    # Extract description and usage from module docstring
    doc_lines = __doc__.split('\n')
    description = []
    for line in doc_lines:
        if line.strip() and not line.startswith('Usage:'):
            description.append(line)
        if line.startswith('Usage:'):
            break

    parser = argparse.ArgumentParser(
        description='A terminal browser for testing printable width of unicode.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Interactive Keys:
  Navigation:
    k, y, UP          Scroll backward 1 line
    j, e, ENTER, DOWN Scroll forward 1 line
    f, SPACE, PGDOWN  Scroll forward 1 page
    b, PGUP           Scroll backward 1 page
    F, SHIFT-DOWN     Scroll forward 10 pages
    B, SHIFT-UP       Scroll backward 10 pages
    HOME              Go to top
    G, END            Go to bottom
    Ctrl-L            Refresh screen

  Mode Switching:
    0                 Exit VS mode (return to normal mode)
    1                 Narrow width (normal) / Narrow base filter (VS mode)
    2                 Wide width (normal) / Wide base filter (VS mode)
    5                 Switch to VS-15 mode (text style)
    6                 Switch to VS-16 mode (emoji style)
    c                 Toggle combining character mode
    w                 Toggle with/without variation selector (VS mode only)

  Display Adjustment:
    -, _              Decrease character name display length by 2
    +, =              Increase character name display length by 2
    v                 Select Unicode version

  Exit:
    q, Q              Quit browser

Notes:
  Only one of --combining, --vs15, or --vs16 can be used at a time.
  The --without-vs option only applies when using --vs15 or --vs16.

  In VS mode, the display shows:
    - W/VS: Characters displayed with variation selector
    - WO/VS: Base characters displayed without variation selector
""")

    parser.add_argument('--wide', metavar='<n>', type=str, default=None,
                        help='Browser 1 or 2 character-wide cells.')
    parser.add_argument('--alignment', metavar='<str>', type=str, default='left',
                        help='Choose left or right alignment. (default: left)')

    # Mutually exclusive group for mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--combining', action='store_true',
                            help='Use combining character generator.')
    mode_group.add_argument('--vs15', action='store_true',
                            help='Browse emoji variation sequences with VS-15 (text style).')
    mode_group.add_argument('--vs16', action='store_true',
                            help='Browse emoji variation sequences with VS-16 (emoji style).')

    parser.add_argument('--without-vs', action='store_true',
                        help='Display base characters without variation selector.')

    args = parser.parse_args()

    # Convert to docopt-style dict format for compatibility with validate_args
    return {
        '--wide': args.wide,
        '--alignment': args.alignment,
        '--combining': args.combining,
        '--vs15': args.vs15,
        '--vs16': args.vs16,
        '--without-vs': args.without_vs,
        '--help': False,  # argparse handles this automatically
    }


if __name__ == '__main__':
    sys.exit(main(validate_args(parse_args())))
