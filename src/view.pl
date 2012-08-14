#!/usr/bin/perl

print "<html><body> @ARGV\n";

# collects information out of the log file.

while ($_=<>) {
  print "<hr> $_ <hr>\n" if /^EPOCH OVER/;
  s/\@[0-9a-f]+//g;
  s/EQ> @ [0-9a-f]+/EQ>/;

  # capture state about the node
  $name=$1 if /0_0 name=<NameID::(.*)>/;
  $names{$name}=$_ if /0_0 stat=/;
  $cpe{$name}=$_ if /0_0 cpe=EQ:-(.*)\/EQ$/;
  if (/0_0 rtbl=<Node--\d+, <NameID::([a-zA-Z0-9]+)> :: EQ:-(.*)\/EQ>$/ && length($2)>0) {
    my $other=$1; my $eqn=$2;
    print STDERR "duplicate $name-$other declaration\n" if exists $eqn{"$name-$other"};
    $eqn=~s/&/&amp;/g;
    $eqn=~s/</&lt;/g;
    $eqn=~s/>/&gt;/g;
    $eqn{"$name-$other"}=$eqn;
  }
  next unless /0_0 nghb=<(.*)>/;

  # process the neighbours list.
  @neighbours=split /\|+/, $1;
  die "neighbourhood format changed '$1'" unless shift(@neighbours) eq 'Neighbourhood--';

  print "<h3> $name </h3>\n<p>$names{$name}</p><table>\n";

  foreach(@neighbours) {
    report_tree_level($_);
  }
  print "</table>";
}
print "</body></html>\n";
exit 0;

sub report_tree_level {
  $_ = $_[0];
  s/<NameID::([a-zA-Z0-9]+)>/$1/g;
  /^(\d+)<Ring--L::(\d+)#(.*), R::(\d+)#(.*)>/ or die "$_ isn't a level report\n";
  my %v=(level=>$1, numleft=>$2, namesleft=>$3, numright=>$4, namesright=>$5);
  my @ls = split /[, ]+/,$v{namesleft};
  @ls = map { exists $eqn{"$name-$_"} ? '<abbr title="'.$eqn{"$name-$_"}.'"'.">$_</abbr>" : $_ } @ls;
  my @rs = split /[, ]+/,$v{namesright};
  @rs = map { exists $eqn{"$name-$_"} ? '<abbr title="'.$eqn{"$name-$_"}.'"'.">$_</abbr>" : $_ } @rs;
  $,=",";
  die "messed up with $name::L $v{namesleft} \n @ls \n $#ls != $v{numleft}" unless $#ls == $v{numleft}-1;
  die "messed up with $name::R $v{namesright} \n @rs" unless $#ls == $v{numright}-1;

  print "<tr><td>$v{level}</td><td>",
    join(', ',@ls),"</td><td>",join(', ',@rs),"</td></tr>\n";
}
