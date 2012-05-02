#!/usr/bin/perl
# parses the output of a check2py | __main__.py run and ensures that 
#  all the retrieved samples match with the pcap data.


while (<>) {
  if (/^._@ ([0-9.]+) - \['(\d+)'\] - <@\:=(.*)@>/) {
    my ($nonce, $uid, $data) = ($1,$2,$3);
    $uid{$nonce} = $uid;
    chomp $data;
    $data =~ s/=//g;
    die "no data parsed $_" unless length($data)>0;
    $data{$nonce} = $data;
  }
  if (/^\!_! ([0-9.]+) - \[(.*)\]$/) {
    print STDERR "X_X nonce $1 has no corresponding state.\n>> $_\n" unless exists $uid{$1};
    my $u = $uid{$1};
    my $d = $data{$1};
    @test = split /[>)], /, $2;
    $okay=0;
    die "unknown pattern for $_\n" unless $#test>0;
    while (@test) {
      my $d2 = shift @test;
      my $u2 = shift @test;
      $u2 =~ /\['(\d+)',/ or die "unknown uid $u2 in\n>> $_";
      $u2 = $1;
      next unless $u2 == $u;
      $okay++;
      $d2 =~ /\(<@\:(.*)@/ or die "unknown structure $d2 in\n>> $_";
      $okay++ if $1 eq $d;
      print STDERR "# $1" unless $1 eq $d;
    }
    print STDERR "0_0 partial match\n $_ -- $d\n" unless $okay == 2;
  }
}
