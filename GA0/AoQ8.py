from bs4 import BeautifulSoup

html = """
<ul class="products d-none">
<li class="vip sale" data-discount="47"></li>
<li class="featured sale vip" data-discount="36"></li>
<li class="on-sale" data-discount="14"></li>
<li class="featured sale vip" data-discount="27"></li>
<li class="vip sale" data-discount="35"></li>
<li class="featured new" data-discount="11"></li>
<li class="sale featured" data-discount="42"></li>
<li class="featured sale" data-discount="39"></li>
<li class="sale" data-discount="41"></li>
<li class="new" data-discount="19"></li>
<li class="featured sale vip" data-discount="8"></li>
<li class="on-sale" data-discount="34"></li>
<li class="sale" data-discount="24"></li>
<li class="vip sale" data-discount="30"></li>
<li class="featured new" data-discount="16"></li>
<li class="sale featured" data-discount="36"></li>
<li class="featured" data-discount="16"></li>
<li class="on-sale" data-discount="44"></li>
<li class="featured new" data-discount="36"></li>
<li class="on-sale" data-discount="48"></li>
</ul>
"""

soup = BeautifulSoup(html, "html.parser")

# Select elements having BOTH featured and sale classes
items = soup.select(".featured.sale")

# Sum their data-discount values
total = sum(int(item["data-discount"]) for item in items)

print("Sum of discounts:", total)