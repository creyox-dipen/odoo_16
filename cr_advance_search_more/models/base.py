# -*- coding: utf-8 -*-
# Part of Creyox Technologies.
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)


class Base(models.AbstractModel):
    """Abstract model extending base to support advance search modes and multi-word searching on _name_search and name_search."""

    _inherit = "base"

    @api.model
    def _name_search(self, name="", args=None, operator="ilike", limit=100, name_get_uid=None):
        """Override _name_search to support multi-word search based on active search_mode across all Odoo models."""
        search_mode = self.env.context.get("cr_search_mode", "default")
        _logger.info(
            "[CR_SEARCH] _name_search on '%s' | name='%s' | operator='%s' | cr_search_mode='%s' | args=%s",
            self._name,
            name,
            operator,
            search_mode,
            args,
        )
        if (
            name
            and isinstance(name, str)
            and operator in ("ilike", "=ilike", "like", "=", "=like")
            and search_mode in ("and", "or")
        ):
            keywords = [word for word in name.strip().split() if word]

            if len(keywords) > 1:
                _logger.info(
                    "[CR_SEARCH] Multi-word _name_search on model '%s' with mode '%s' for keywords: %s",
                    self._name,
                    search_mode,
                    keywords,
                )
                if search_mode == "and":
                    result_ids_list = []
                    for keyword in keywords:
                        keyword_res = super(
                            Base, self.with_context(cr_search_mode="default")
                        )._name_search(
                            name=keyword,
                            args=args,
                            operator=operator,
                            limit=None,
                            name_get_uid=name_get_uid,
                        )
                        keyword_ids = list(keyword_res)
                        _logger.info(
                            "[CR_SEARCH] AND mode keyword '%s' matched %s IDs on '%s'",
                            keyword,
                            len(keyword_ids),
                            self._name,
                        )
                        result_ids_list.append(keyword_ids)

                    if result_ids_list:
                        common_ids = set(result_ids_list[0])
                        for res_ids in result_ids_list[1:]:
                            common_ids &= set(res_ids)

                        final_ids = [
                            rec_id for rec_id in result_ids_list[0] if rec_id in common_ids
                        ]
                        _logger.info(
                            "[CR_SEARCH] AND mode final intersected IDs count: %s on '%s'",
                            len(final_ids),
                            self._name,
                        )
                        return final_ids[:limit] if limit else final_ids
                    return []

                elif search_mode == "or":
                    seen_ids = set()
                    final_ids = []
                    for keyword in keywords:
                        keyword_res = super(
                            Base, self.with_context(cr_search_mode="default")
                        )._name_search(
                            name=keyword,
                            args=args,
                            operator=operator,
                            limit=limit,
                            name_get_uid=name_get_uid,
                        )
                        for rec_id in keyword_res:
                            if rec_id not in seen_ids:
                                seen_ids.add(rec_id)
                                final_ids.append(rec_id)
                                if limit and len(final_ids) >= limit:
                                    break
                        if limit and len(final_ids) >= limit:
                            break
                    _logger.info(
                        "[CR_SEARCH] OR mode union IDs count: %s on '%s'",
                        len(final_ids),
                        self._name,
                    )
                    return final_ids

        res = super(Base, self)._name_search(
            name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid
        )
        return res

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Override name_search to support multi-word search based on active search_mode across all Odoo models."""
        search_mode = self.env.context.get("cr_search_mode", "default")
        _logger.info(
            "[CR_SEARCH] name_search called on model '%s' | name='%s' | cr_search_mode='%s' | args=%s",
            self._name,
            name,
            search_mode,
            args,
        )

        if (
            name
            and isinstance(name, str)
            and operator in ("ilike", "=ilike", "like", "=", "=like")
            and search_mode in ("and", "or", "not")
        ):
            keywords = [word for word in name.strip().split() if word]

            if search_mode == "not" and keywords:
                _logger.info(
                    "[CR_SEARCH] NOT mode name_search on model '%s' for keywords: %s",
                    self._name,
                    keywords,
                )
                excluded_ids = set()
                for keyword in keywords:
                    keyword_results = super(
                        Base, self.with_context(cr_search_mode="default")
                    ).name_search(
                        name=keyword, args=args, operator=operator, limit=None
                    )
                    for rec in keyword_results:
                        excluded_ids.add(rec[0])

                not_domain = (args or []) + [("id", "not in", list(excluded_ids))]
                res = super(
                    Base, self.with_context(cr_search_mode="default")
                ).name_search(
                    name="", args=not_domain, operator=operator, limit=limit
                )
                _logger.info(
                    "[CR_SEARCH] NOT mode name_search on model '%s' returning %s results",
                    self._name,
                    len(res),
                )
                return res

            if len(keywords) > 1:
                _logger.info(
                    "[CR_SEARCH] Multi-word name_search on model '%s' with mode '%s' for keywords: %s",
                    self._name,
                    search_mode,
                    keywords,
                )

                if search_mode == "and":
                    result_sets = []
                    for keyword in keywords:
                        keyword_results = super(
                            Base, self.with_context(cr_search_mode="default")
                        ).name_search(
                            name=keyword, args=args, operator=operator, limit=None
                        )
                        _logger.info(
                            "[CR_SEARCH] AND mode keyword '%s' matched %s results on '%s'",
                            keyword,
                            len(keyword_results),
                            self._name,
                        )
                        result_sets.append({rec[0]: rec for rec in keyword_results})

                    if result_sets:
                        common_ids = set(result_sets[0].keys())
                        for res_dict in result_sets[1:]:
                            common_ids &= set(res_dict.keys())

                        final_results = []
                        for rec in result_sets[0].values():
                            if rec[0] in common_ids:
                                final_results.append(rec)
                                common_ids.remove(rec[0])
                        _logger.info(
                            "[CR_SEARCH] AND mode final intersected results count: %s on '%s'",
                            len(final_results),
                            self._name,
                        )
                        return final_results[:limit] if limit else final_results
                    return []

                elif search_mode == "or":
                    seen_ids = set()
                    final_results = []
                    for keyword in keywords:
                        keyword_results = super(
                            Base, self.with_context(cr_search_mode="default")
                        ).name_search(
                            name=keyword, args=args, operator=operator, limit=limit
                        )
                        _logger.info(
                            "[CR_SEARCH] OR mode keyword '%s' matched %s results on '%s'",
                            keyword,
                            len(keyword_results),
                            self._name,
                        )
                        for rec in keyword_results:
                            if rec[0] not in seen_ids:
                                seen_ids.add(rec[0])
                                final_results.append(rec)
                                if limit and len(final_results) >= limit:
                                    break
                        if limit and len(final_results) >= limit:
                            break
                    _logger.info(
                        "[CR_SEARCH] OR mode union results count: %s on '%s'",
                        len(final_results),
                        self._name,
                    )
                    return final_results

        res = super(Base, self).name_search(
            name=name, args=args, operator=operator, limit=limit
        )
        return res
