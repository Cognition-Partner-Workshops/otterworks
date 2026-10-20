#!/usr/bin/perl
# Daily FX desk report. Apache runs this through mod_cgi; the session
# check is mod_auth_ldap in front of /cgi-bin, and the page is cached by
# mod_expires for an hour.
use strict;
use warnings;
use lib '/var/www/fx-report/lib';
use CGI qw(:standard escapeHTML);
use POSIX qw(strftime);
use FxReport::Rates;

my $SPOOL = '/mnt/rates-out';
my $day = param('day') || strftime('%Y-%m-%d', localtime(time - 86400));
$day = '' unless $day =~ /^\d{4}-\d\d-\d\d$/;
my ($y, $m, $d) = split /-/, $day;
my $prev_day = strftime('%Y-%m-%d', 0, 0, 12, $d - 1, $m - 1, $y - 1900);

my $today = FxReport::Rates::read_day("$SPOOL/rates-$day.csv");
my $prev  = FxReport::Rates::read_day("$SPOOL/rates-$prev_day.csv");

print header(-type => 'text/html', -charset => 'utf-8');
print start_html(-title => "FX desk report $day", -style => { -code => 'body{font-family:Arial;margin:2em}td{padding:3px 10px}' });
print h1("FX desk report"), p("Business date " . escapeHTML($day) . ", user " . escapeHTML($ENV{REMOTE_USER} || 'unknown'));
if (!$today) {
    print p("No rates file for this day yet.");
} else {
    print '<table><tr><th>Pair</th><th>Close</th><th>Average mid</th><th>Range</th><th>Change</th></tr>';
    for my $r (@{ FxReport::Rates::moves($today, $prev) }) {
        my $chg = defined $r->{chg_pct} ? sprintf('%+.3f%%', $r->{chg_pct}) : 'n/a';
        printf "<tr><td>%s</td><td>%s</td><td>%s</td><td>%.5f</td><td>%s</td></tr>\n",
            escapeHTML($r->{pair}), $r->{close}, $r->{avg}, $r->{range}, $chg;
    }
    print '</table>';
}
print end_html;
