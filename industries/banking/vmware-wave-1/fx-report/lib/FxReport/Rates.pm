package FxReport::Rates;
use strict;
use warnings;

# Reads the rates-batch output and works out day-on-day moves per pair.

sub read_day {
    my ($path) = @_;
    open my $fh, '<', $path or return undef;
    my %r;
    my $hdr = <$fh>;
    while (my $line = <$fh>) {
        chomp $line;
        next unless length $line;
        my ($pair, $open, $high, $low, $close, $avg, $ticks) = split /,/, $line;
        $r{$pair} = { open => $open, high => $high, low => $low, close => $close, avg => $avg, ticks => $ticks };
    }
    close $fh;
    return \%r;
}

sub moves {
    my ($today, $prev) = @_;
    my @rows;
    for my $pair (sort keys %$today) {
        my $t = $today->{$pair};
        my $p = $prev && $prev->{$pair};
        my $chg = $p ? ($t->{close} - $p->{close}) / $p->{close} * 100 : undef;
        push @rows, { pair => $pair, close => $t->{close}, avg => $t->{avg},
                      range => $t->{high} - $t->{low}, chg_pct => $chg };
    }
    return \@rows;
}

1;
