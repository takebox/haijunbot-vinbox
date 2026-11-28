#!/bin/bash

# Get the absolute path of the script's directory
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
# Get the project root directory
PROJECT_ROOT=$(dirname "$SCRIPT_DIR")

# Merge markdown files
awk 'FNR==1 && NR>1 {print "\n\n---\n"} {print}' $PROJECT_ROOT/docs/haijunbot_book/*.md > /tmp/combined_book.md
# Uniformly replace consecutive newlines immediately followed by a heading with two newlines, i.e. "\n+^#" -> "\n\n#"
perl -0777 -i -pe 's/\n+(?=^#)/\n\n/mg' /tmp/combined_book.md
# Apply list blank-line correction rules only outside code blocks, to avoid affecting leading '-' or numbered lists inside code
perl -0777 -i -pe '
  my $text = $_;
  my $out = "";
  my $last = 0;

  # Process by segment: fenced code blocks (``` or ~~~) are kept as-is; list blank-line correction rules apply to the remaining text segments
  while ($text =~ /(.*?)(^[ \t]*([`~]{3,}).*?\n.*?^\s*\3[ \t]*\s*$)/gms) {
    my ($pre, $code) = ($1, $2);

    # Rule 1: if a description line ending with a colon/fullwidth colon is immediately followed by a list item, add a blank line
    $pre =~ s/(?m)(^.*[：:][ \t\*\`_~]*\n)(?=(?:[ \t]*(?:[-*+]|\d+[.)）])\s))/$1\n/g;

    # Rule 2: if a normal paragraph is immediately followed by a list item, add a blank line (excluding headings/quotes/code fences/tables/existing lists/horizontal rules)
    $pre =~ s/(?m)(^(?![ \t]*(?:[#>`]|\||(?:[-*+]|\d+[.)）])\s|-{3,}\s*$)).+\n)(?=(?:[ \t]*(?:[-*+]|\d+[.)）])\s))/$1\n/g;

    $out .= $pre . $code;
    $last = pos($text);
  }

  # Process the last segment (trailing text not inside a code block)
  my $tail = substr($text, $last);
  $tail =~ s/(?m)(^.*[：:][ \t\*\`_~]*\n)(?=(?:[ \t]*(?:[-*+]|\d+[.)）])\s))/$1\n/g;
  $tail =~ s/(?m)(^(?![ \t]*(?:[#>`]|\||(?:[-*+]|\d+[.)）])\s|-{3,}\s*$)).+\n)(?=(?:[ \t]*(?:[-*+]|\d+[.)）])\s))/$1\n/g;

  $_ = $out . $tail;
' /tmp/combined_book.md
# Add a blank line before a table header (only before the header row, when the next line is a separator)
perl -0777 -i -pe 's/(?m)(^.+\S.*\n)(?=(?:[ \t]*\|.*\|\s*\n[ \t]*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$))/$1\n/g' /tmp/combined_book.md

# Call build_pdf.sh to generate the PDF, specifying the output filename as HaijunBot_Book.pdf in the current directory
"$SCRIPT_DIR/build_pdf.sh" /tmp/combined_book.md ./HaijunBot_Book.pdf
