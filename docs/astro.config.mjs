import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import rehypeExternalLinks from 'rehype-external-links';

export default defineConfig({
	markdown: {
		rehypePlugins: [
			[rehypeExternalLinks, { target: '_blank', rel: ['noopener', 'noreferrer'] }]
		],
	},
	site: 'https://opencitations.github.io',
	base: '/lode',

	integrations: [
		starlight({
			title: 'Lode',
			description: 'New reengineered version of LODE, maintained by OpenCitations',

			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/opencitations/lode' },
			],

			sidebar: [
				{
					label: 'Guides',
					items: [
						{ label: 'Getting started', slug: 'getting_started' },
					],
				},
			],
		}),
	],
});
