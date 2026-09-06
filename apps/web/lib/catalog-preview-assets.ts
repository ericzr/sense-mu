import type { CatalogScene } from "./catalog-mock-data";

export type CatalogPreviewAsset = {
  url: string;
  aspectRatio: number;
  dataset: string;
  sample: string;
  license: string;
  sourceUrl: string;
};

const catalogPreviewAssets: Partial<Record<CatalogScene, CatalogPreviewAsset>> = {
  "road-surface": {
    url: "/catalog-real-road-surface.png", aspectRatio: 352 / 288, dataset: "Road Traversing Knowledge", sample: "RTK image/000000112.png", license: "CC BY 4.0", sourceUrl: "https://doi.org/10.17632/hssswvmjwf.1",
  },
  "road-safety": {
    url: "/catalog-real-road-safety.jpg", aspectRatio: 640 / 427, dataset: "Open Images", sample: "Open Images 9c7e9f0b7713352b", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/mkumm/2840891484",
  },
  "road-slope": {
    url: "/catalog-real-road-slope.jpg", aspectRatio: 640 / 480, dataset: "Open Images", sample: "Open Images 0376af43cb012d3f", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/hugo90/2771912825",
  },
  "road-environment": {
    url: "/catalog-real-road-environment.png", aspectRatio: 352 / 288, dataset: "Road Traversing Knowledge", sample: "RTK image/000000526.png", license: "CC BY 4.0", sourceUrl: "https://doi.org/10.17632/hssswvmjwf.1",
  },
  tunnel: {
    url: "/catalog-real-tunnel.jpg", aspectRatio: 480 / 640, dataset: "Open Images", sample: "Open Images 0fa91664f038fbc8", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/larrywkoester/15452965777",
  },
  bridge: {
    url: "/catalog-real-bridge.jpg", aspectRatio: 640 / 480, dataset: "Open Images", sample: "Open Images 00a159a661a2f5aa", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/feelingdoing/13645764903",
  },
  "urban-illegal": {
    url: "/catalog-real-urban-illegal.jpg", aspectRatio: 640 / 427, dataset: "Open Images", sample: "Open Images 00794645d77184eb", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/stevenpisano/15256561208",
  },
  "urban-sanitation": {
    url: "/catalog-real-urban-sanitation.jpg", aspectRatio: 640 / 480, dataset: "TACO", sample: "TACO 1321", license: "CC BY 4.0", sourceUrl: "https://github.com/pedropro/TACO",
  },
  "urban-construction-waste": {
    url: "/catalog-real-urban-construction-waste.jpg", aspectRatio: 640 / 480, dataset: "Open Images", sample: "Open Images 03edd1fdd321dd39", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/annaoakley/3022479439",
  },
  "urban-site": {
    url: "/catalog-real-urban-site.jpg", aspectRatio: 640 / 482, dataset: "Open Images", sample: "Open Images 496a5b694439b447", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/jaxstrong/10311778426",
  },
  "urban-advertising": {
    url: "/catalog-real-urban-advertising.jpg", aspectRatio: 640 / 480, dataset: "Open Images", sample: "Open Images 03c35bdfffbea53f", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/bizmac/16332584327",
  },
  "urban-municipal": {
    url: "/catalog-real-urban-municipal.jpg", aspectRatio: 640 / 480, dataset: "Open Images", sample: "Open Images 97293a439963c5f2", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/leopoldstadt/5624935537",
  },
  "urban-water": {
    url: "/catalog-real-urban-water.jpg", aspectRatio: 480 / 640, dataset: "TACO", sample: "TACO 1107", license: "CC BY 4.0", sourceUrl: "https://github.com/pedropro/TACO",
  },
  "urban-ecology": {
    url: "/catalog-real-urban-ecology.jpg", aspectRatio: 640 / 480, dataset: "Open Images", sample: "Open Images 9ff070bff835a3b9", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/armydre2008/10810196273",
  },
  "urban-fire": {
    url: "/catalog-real-urban-fire.jpg", aspectRatio: 640 / 480, dataset: "Open Images", sample: "Open Images 2afab7192939c56d", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/glennbatuyong/4729261348",
  },
  "urban-crowd": {
    url: "/catalog-real-urban-crowd.jpg", aspectRatio: 640 / 427, dataset: "Open Images", sample: "Open Images 0162246ca3c39e68", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/magharebia/6431185703",
  },
  "urban-traffic": {
    url: "/catalog-real-urban-traffic.jpg", aspectRatio: 640 / 480, dataset: "Open Images", sample: "Open Images 1ab5db67d31e2038", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/24810925@N04/2648287727",
  },
  "urban-greening": {
    url: "/catalog-real-urban-greening.jpg", aspectRatio: 640 / 427, dataset: "Open Images", sample: "Open Images 2e49ef1ef93f6fd6", license: "CC BY 2.0", sourceUrl: "https://www.flickr.com/photos/br1dotcom/2914696201",
  },
};

export function getCatalogPreviewAsset(scene: CatalogScene) {
  return catalogPreviewAssets[scene] ?? null;
}
