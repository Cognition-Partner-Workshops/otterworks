package FxReport::Rates;
use strict;
use warnings;

# Reads the rates-batch output and works out day-on-day moves per pair.

sub read_day {
    my ($path) = @_;
    open my $fh, '<', $path or return undef;
    my %r;
    my $hdr = <$fh>;
    chomp $hdr;
    my @columns = split /,/, $hdr;
    my ($file_day) = $path =~ /rates-(\d{4}-\d\d-\d\d)\.csv$/;
    while (my $line = <$fh>) {
        chomp $line;
        next unless length $line;
        my %values;
        @values{@columns} = split /,/, $line;
        my ($pair, $open, $high, $low, $close, $avg, $ticks, $business_date) =
            @values{qw(pair open high low close avg_mid ticks business_date)};
        $r{$pair} = { open => $open, high => $high, low => $low, close => $close, avg => $avg, ticks => $ticks,
                      business_date => $business_date || $file_day };
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
        push @rows, { pair => $pair, close => $t->{close}, avg => $t->{avg}, business_date => $t->{business_date},
                      range => $t->{high} - $t->{low}, chg_pct => $chg,
                      previous_business_date => $p ? $p->{business_date} : undef };
    }
    return \@rows;
}

1;
