import * as yup from 'yup';
import sanitizeHtml from 'sanitize-html';
import {
  DEFAULT_LIMIT,
  DEFAULT_PAGE,
  LIMIT_OPTIONS,
} from '../constants/constants';

const querySchema = yup.object().shape({
  page: yup.number().integer().positive().min(1).default(DEFAULT_PAGE),
  limit: yup
    .number()
    .integer()
    .positive()
    .min(1)
    .default(DEFAULT_LIMIT)
    .test('is-valid-limit', 'Invalid limit value', (value) =>
      LIMIT_OPTIONS.includes(value || DEFAULT_LIMIT)
    ),
  q: yup.string().trim().default(''),
  type: yup.string().trim().notRequired(),
  categories: yup.string().trim().notRequired(),
});

const sanitizeQuery = (query: Record<string, any>) => {
  const sanitizedQuery = { ...query };
  if (sanitizedQuery.q) {
    sanitizedQuery.q = sanitizeHtml(sanitizedQuery.q, {
      allowedTags: [],
      allowedAttributes: {},
    });
  }
  return sanitizedQuery;
};

const validateQuery = (searchParams: URLSearchParams) => {
  const query = Object.fromEntries(searchParams.entries());
  if (Object.keys(query).length === 0) {
    return query;
  }

  let validatedQuery: { [key: string]: any } = {};
  Object.keys(querySchema.fields).forEach((key) => {
    if (query[key] !== undefined) {
      try {
        validatedQuery[key] = (querySchema.fields as any)[key].validateSync(
          query[key],
          {
            stripUnknown: true,
            abortEarly: false,
          }
        );
      } catch (error) {
        validatedQuery[key] = (querySchema.fields as any)[key].default();
      }
    }
  });

  validatedQuery = sanitizeQuery(validatedQuery);
  return validatedQuery;
};

export default validateQuery;
