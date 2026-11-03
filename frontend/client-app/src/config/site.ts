export interface MenuColumn { title: string; links: { label: string; href: string }[] }
export interface Department { slug: string; label: string; href: string; columns: MenuColumn[]; feature?: { title: string; href: string; image: string } }

const cat = (dept: string, label: string, category = label) =>
  ({ label, href: `/c/${dept}?category=${encodeURIComponent(category.toLowerCase())}` });
const fit = (dept: string, label: string) => ({ label, href: `/c/${dept}?fit=${encodeURIComponent(label.toLowerCase())}` });

export const departments: Department[] = [
  {
    slug: "women", label: "Women", href: "/c/women",
    columns: [
      { title: "Shop by category", links: [cat("women", "Dresses"), cat("women", "Sweaters"), cat("women", "Shirts & Blouses"), cat("women", "Skirts"), cat("women", "Tees & Tanks"), cat("women", "Jeans"), cat("women", "Coats & Jackets"), cat("women", "Activewear"), cat("women", "Sleepwear")] },
      { title: "Featured", links: [{ label: "New Arrivals", href: "/c/new-arrivals?department=women" }, { label: "Black Friday Deals", href: "/sale?department=women" }, { label: "Essentials Forever", href: "/c/essentials-forever?department=women" }, { label: "Maternity", href: "/c/maternity" }] },
      { title: "Shop by fit", links: [fit("women", "Skinny"), fit("women", "Straight"), fit("women", "Wide-Leg"), fit("women", "Relaxed"), fit("women", "Wrap")] },
    ],
    feature: { title: "Knits for cold mornings", href: "/c/women?category=sweaters", image: "/images/editorial/editorial-12.webp" },
  },
  {
    slug: "men", label: "Men", href: "/c/men",
    columns: [
      { title: "Shop by category", links: [cat("men", "Tees"), cat("men", "Shirts"), cat("men", "Hoodies & Sweatshirts"), cat("men", "Pants & Chinos"), cat("men", "Jeans"), cat("men", "Jackets & Coats"), cat("men", "Sweaters"), cat("men", "Activewear")] },
      { title: "Featured", links: [{ label: "New Arrivals", href: "/c/new-arrivals?department=men" }, { label: "Black Friday Deals", href: "/sale?department=men" }, { label: "Essentials Forever", href: "/c/essentials-forever?department=men" }] },
      { title: "Shop by fit", links: [fit("men", "Slim"), fit("men", "Straight"), fit("men", "Athletic Taper"), fit("men", "Relaxed")] },
    ],
    feature: { title: "Layers that work hard", href: "/c/men?category=jackets+%26+coats", image: "/images/editorial/editorial-23.webp" },
  },
  {
    slug: "kids", label: "Kids", href: "/c/kids",
    columns: [
      { title: "Shop by size", links: ["4", "6", "8", "10", "12", "14"].map((s) => ({ label: `Size ${s}`, href: `/c/kids?size=${s}` })) },
      { title: "Featured", links: [{ label: "New Arrivals", href: "/c/new-arrivals?department=kids" }, { label: "Kids on Sale", href: "/sale?department=kids" }] },
    ],
    feature: { title: "Play-proof basics", href: "/c/kids", image: "/images/editorial/editorial-17.webp" },
  },
  {
    slug: "baby", label: "Baby", href: "/c/baby",
    columns: [
      { title: "Shop by age", links: ["0-3M", "3-6M", "6-12M", "12-18M", "18-24M"].map((s) => ({ label: s, href: `/c/baby?size=${s}` })) },
      { title: "Featured", links: [{ label: "Baby on Sale", href: "/sale?department=baby" }] },
    ],
  },
  { slug: "maternity", label: "Maternity", href: "/c/maternity", columns: [{ title: "Maternity", links: [{ label: "Shop all maternity", href: "/c/maternity" }] }] },
  {
    slug: "denim", label: "Denim", href: "/c/denim",
    columns: [{ title: "Shop denim", links: [{ label: "Women's jeans", href: "/c/denim?department=women" }, { label: "Men's jeans", href: "/c/denim?department=men" }, { label: "Light wash", href: "/c/denim?color=blue" }, { label: "Black denim", href: "/c/denim?color=black" }] }],
  },
  { slug: "activewear", label: "Activewear", href: "/c/activewear", columns: [{ title: "Otter Active", links: [{ label: "Women", href: "/c/activewear?department=women" }, { label: "Men", href: "/c/activewear?department=men" }] }] },
  { slug: "sale", label: "Sale", href: "/sale", columns: [{ title: "Sale", links: [{ label: "All sale", href: "/sale" }, { label: "Women", href: "/sale?department=women" }, { label: "Men", href: "/sale?department=men" }, { label: "Kids", href: "/sale?department=kids" }, { label: "Baby", href: "/sale?department=baby" }] }] },
];

export const DEPARTMENT_SLUGS = ["women", "men", "kids", "baby", "maternity"];
