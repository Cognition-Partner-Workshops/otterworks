#!/usr/bin/perl
# Daily FX desk report. Apache runs this through mod_cgi; the session
# check is mod_auth_ldap in front of /cgi-bin, and the page is cached by
# mod_expires for an hour.
use strict;
use warnings;
use lib '/var/www/fx-report/lib';
use CGI qw(:standard escapeHTML);
use POSIX qw(strftime);
use Time::Local qw(timegm);
use FxReport::Rates;

my $SPOOL = $ENV{RATES_OUT_DIR} || '/mnt/rates-out';
my $day = param('day') || strftime('%Y-%m-%d', gmtime(time - 86400));
my $epoch = eval {
    die "invalid date" unless $day =~ /^\d{4}-\d\d-\d\d$/;
    my ($year, $month, $date) = split /-/, $day;
    timegm(0, 0, 12, $date, $month - 1, $year);
};
if ($@) {
    print header(-status => '400 Bad Request', -type => 'text/html', -charset => 'utf-8');
    print start_html('FX desk report'), p('Invalid report date'), end_html;
    exit;
}
my ($y, $m, $d) = split /-/, $day;
my $prev_day = strftime('%Y-%m-%d', gmtime($epoch - 86400));

my $today = FxReport::Rates::read_day("$SPOOL/rates-$day.csv");
my $prev  = FxReport::Rates::read_day("$SPOOL/rates-$prev_day.csv");

print header(-type => 'text/html', -charset => 'utf-8');
print start_html(-title => "FX desk report $day", -style => { -code => 'body{font-family:Arial;margin:2em}td{padding:3px 10px}' });
print h1("FX desk report"), p("Report file date " . escapeHTML($day) . ", user " . escapeHTML($ENV{REMOTE_USER} || 'unknown'));
if (!$today) {
    print p("No rates file for this day yet.");
} else {
    print '<table><tr><th>Pair</th><th>Close</th><th>Average mid</th><th>Range</th><th>Change</th></tr>';
    for my $r (@{ FxReport::Rates::moves($today, $prev) }) {
        my $chg = defined $r->{chg_pct} ? sprintf('%+.3f%%', $r->{chg_pct}) : 'n/a';
        my $date = escapeHTML($r->{business_date} || $day);
        $chg .= " ($date vs " . escapeHTML($r->{previous_business_date} || $prev_day) . ")"
            if defined $r->{chg_pct};
        printf "<tr><td>%s</td><td>%s (%s)</td><td>%s (%s)</td><td>%.5f (%s)</td><td>%s</td></tr>\n",
            escapeHTML($r->{pair}), $r->{close}, $date, $r->{avg}, $date, $r->{range}, $date, $chg;
    }
    print '</table>';
}
print end_html;
