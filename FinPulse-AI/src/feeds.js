// RSS feed sources grouped by category. All free, no API key required.
// If a feed is geo-blocked or down, the app just skips it gracefully.
module.exports = {
  categories: [
    {
      id: 'markets',
      label: 'Markets / Stocks',
      icon: '📈',
      feeds: [
        'https://www.cnbc.com/id/20910258/device/rss/rss.html',
        'http://feeds.marketwatch.com/marketwatch/topstories/',
        'https://finance.yahoo.com/news/rssindex'
      ]
    },
    {
      id: 'crypto',
      label: 'Crypto',
      icon: '🪙',
      feeds: [
        'https://www.coindesk.com/arc/outboundfeeds/rss/',
        'https://cointelegraph.com/rss',
        'https://cryptoslate.com/feed/'
      ]
    },
    {
      id: 'forex',
      label: 'Forex',
      icon: '💱',
      feeds: [
        'https://www.fxstreet.com/rss/news',
        'https://www.investing.com/rss/news_1.rss'
      ]
    },
    {
      id: 'economy',
      label: 'Economy / Macro',
      icon: '🏛️',
      feeds: [
        'https://www.cnbc.com/id/20910258/device/rss/rss.html',
        'https://www.investing.com/rss/news_14.rss'
      ]
    },
    {
      id: 'commodities',
      label: 'Commodities',
      icon: '🛢️',
      feeds: [
        'https://www.investing.com/rss/news_11.rss',
        'http://feeds.marketwatch.com/marketwatch/marketpulse/'
      ]
    },
    {
      id: 'business',
      label: 'Business',
      icon: '💼',
      feeds: [
        'https://www.cnbc.com/id/100003114/device/rss/rss.html',
        'https://feeds.bbci.co.uk/news/business/rss.xml'
      ]
    }
  ]
};
