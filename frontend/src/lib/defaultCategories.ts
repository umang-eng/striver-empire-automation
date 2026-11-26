import { CategoryGroup } from "./types";

export const DEFAULT_CATEGORY_GROUPS: CategoryGroup[] = [
  {
    id: "mens",
    label: "Men's",
    main_templates: ["men 5%", "men 10%", "men 15%"],
    subcategories: [
      { name: "Shirt", template: "men shirt 5%" },
      { name: "Formal Pants", template: "men formal pants 5%" },
      { name: "T-shirt", template: "men t-shirt 5%" },
      { name: "Jeans", template: "men jeans 5%" },
      { name: "Shorts", template: "men shorts 5%" },
      { name: "Lower", template: "men lower 5%" },
      { name: "Blazers", template: "men blazers 5%" },
      { name: "Sando", template: "men sando 5%" },
      { name: "Basket Jacket", template: "men basket jacket 5%" },
      { name: "Co-ord Sets", template: "men co-ord sets 5%" },
    ],
  },
  {
    id: "womens",
    label: "Women's",
    main_templates: ["women 5%", "women 10%", "women 15%"],
    subcategories: [
      { name: "Shirt's", template: "women shirts 5%" },
      { name: "Formal Pant", template: "women formal pants 5%" },
      { name: "Tops", template: "women tops 5%" },
      { name: "Women Jeans", template: "women jeans 5%" },
      { name: "Blazers", template: "women blazers 5%" },
    ],
  },
  {
    id: "beauty-and-cosmetics",
    label: "Beauty & Cosmetics",
    main_templates: [
      "beauty and cosmetics 5%",
      "beauty and cosmetics 10%",
      "beauty and cosmetics 15%",
    ],
    subcategories: [
      { name: "Beauty and Cosmetic", template: "beauty and cosmetic 5%" },
    ],
  },
  {
    id: "accessories",
    label: "Accessories",
    main_templates: ["accessories 5%", "accessories 10%", "accessories 15%"],
    subcategories: [
      { name: "Belts", template: "accessories belts 5%" },
      { name: "Ties", template: "accessories ties 5%" },
      { name: "Socks", template: "accessories socks 5%" },
      { name: "Cap", template: "accessories cap 5%" },
    ],
  },
  {
    id: "winter",
    label: "Winter",
    main_templates: ["winter 5%", "winter 10%", "winter 15%"],
    subcategories: [
      { name: "Sweater", template: "winter sweater 5%" },
      { name: "Hoodie", template: "winter hoodie 5%" },
      { name: "Jacket", template: "winter jacket 5%" },
      { name: "High Neck", template: "winter high neck 5%" },
    ],
  },
  {
    id: "home-living",
    label: "Home & Living",
    main_templates: [
      "home and living 5%",
      "home and living 10%",
      "home and living 15%",
    ],
    subcategories: [
      { name: "Bedsheets", template: "home and living bedsheets 5%" },
      { name: "Towels", template: "home and living towels 5%" },
      { name: "Foot Mat", template: "home and living foot mat 5%" },
    ],
  },
];
