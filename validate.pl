#!/usr/bin/perl
# parses the output of a check2py | __main__.py run and ensures that 
#  all the retrieved samples match with the pcap data.


while (<>) {
  # we get a line for every sent request. The request has
  # a nonce that uniquely identifies it, and it is based on
  # some $data{nonce} that is expected to return $uid{nonce}
  # (the identifier of the data itself in the store).
  if (/^._@ SEND ([0-9.]+) - \['(\d+)'\] - <@\:=(.*)@>/) {
    my ($nonce, $uid, $data) = ($1,$2,$3);
    $uid{$nonce} = $uid;
    chomp $data;
    $data =~ s/=//g;
    die "no data parsed $_" unless length($data)>0;
    $data{$nonce} = $data;
  }


  # a packet reception has been reported. 
  if (/^\!_! DATA ([0-9.]+) - \[(.*)\]$/) {
    my (           $nonce,      $payload)=($1,$2);
    print STDERR "X_X nonce $1 has no corresponding state.\n>> $_\n" unless exists $uid{$1};
    my $u = $uid{$nonce};
    my $d = $data{$nonce};
    @test = split /[>)], /, $payload;
    $okay=0;
    if (!@test) {
      next if exists $received{$nonce};
      $missing{$nonce}=0 if !exists $missing{$nonce};
      $missing{$nonce}++;
      next;
    }
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
    $received{$nonce}=1;
    delete $missing{$nonce};
    push @valid,$u if $okay==2;
  }
}
@nonces = keys %uid;
print STDERR ">>> $#valid/$#nonces valid replies received.\n";
@missing = keys %missing;
@missing = map {"$_ : $data{$_} : $uid{$_}"} sort @missing;
print join("\n", @missing),"\n";
exit 0;
