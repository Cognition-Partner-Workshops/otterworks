package CustbillDetClock;
# Loaded via PERL5OPT=-MCustbillDetClock for parity runs: when CUSTBILL_NOW is
# set ("YYYY-MM-DD HH:MM:SS", local time), time() and argument-less localtime()
# report that instant. Leaves Perl untouched when CUSTBILL_NOW is unset.
use strict;
use warnings;
use Time::Local qw(timelocal);

BEGIN {
    my $now = $ENV{CUSTBILL_NOW};
    if (defined $now && $now =~ /^(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)$/) {
        my $fixed = timelocal($6, $5, $4, $3, $2 - 1, $1);
        no warnings 'once';
        *CORE::GLOBAL::time      = sub () { $fixed };
        *CORE::GLOBAL::localtime = sub (;$) { CORE::localtime(@_ ? $_[0] : $fixed) };
    }
}

1;
