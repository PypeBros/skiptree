#!/usr/bin/perl
my $i=0;
my ($filename, $timestep, $timebase, $timemax) = @ARGV;

open INPUT,"zcat $filename|" or die "no input found in $filename";

@Tfields = qw(Ivers Iid Iopts Ittl Iproto Isrc Idst TCP Tsrc Tdst Tseq Tack Tlen Tflags Twin Topts);
foreach (@Tfields) {
  $TCP{$_}=$i++;
}

@Ufields = qw(Ivers Iid Iopts Ittl Iproto Isrc Idst UDP Usrc Udst Ulen);
foreach (@Ufields) {
  $UDP{$_}=$i++;
}

@Cfields = qw(Ivers Iid Iopts Ittl Iproto Isrc Idst ICMP Ctype Ccode Cmore);
foreach (@Cfields) {
  $ICMP{$_}=$i++;
}

print "0\n2\n";

$timestep = 1 if !defined $timestep;
while (<INPUT>) {
  @values = split /,/;
  @keypart=();
  if (@values[4]==6) {
    @keypart = map {"Component(Dimension.get('$Tfields[$_]'),'$values[$_]'),"}
      (4,5,6,8,9,13);
  } elsif (@values[4]==0x11) {
    @keypart = map {"Component(Dimension.get('$Ufields[$_]'),'$values[$_]'),"}
      (4,5,6,8,9,10);
  } elsif (@values[4]==1) {
    @keypart = map {"Component(Dimension.get('$Cfields[$_]'),'$values[$_]'),"}
      (4,5,6,8,9);
  }
  next if !@keypart;
  $data = "['$timebase',%\s]";
  $timebase+=$timestep;
  print "1\nSpacePart([@keypart])\n$data\n";

  # see __main__.py
  #   keypart = eval(input()) <- here goes @keypart
  #   purevalues = eval(input() % "self.portno,self.uid")
  #   self.uid+=1
  #   self.__local_node.data_store.add(keypart, purevalues)

  last if (defined $timemax) && $timebase>$timemax;
}

print STDERR "insertion terminated at ($timebase + $timestep > $timemax)\n";
print "0\n3\ninteractive mode enabled\n6\n";
$|=1; # auto-flush STDOUT
while (<STDIN>) {
  print;
}
